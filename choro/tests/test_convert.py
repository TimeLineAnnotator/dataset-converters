"""The tables the converter writes, without TiLiA."""
from fractions import Fraction

import pytest


def test_the_corpus(pieces):
    assert len(pieces) == 295
    assert sum(len(p.rows) for p in pieces.values()) == 44067


def test_durations_are_whole_notes(choro, pieces):
    alvorada = pieces["1_alvorada_WF"]
    assert {r["duration"] for r in alvorada.rows if r["bar_no"] == "1"} == {"0.5"}  # one chord fills a 2/4 bar
    times = choro.chord_times(alvorada.rows)
    assert times[1] == 2 and times[-1] == 168  # 84 bars of two quarter notes


def test_bars_follow_their_chords(choro, built):
    rows = built["1_alvorada_WF"].csvs["measures.csv"][1]
    firsts = [r for r in rows if r["is_first_in_measure"] == "true"]
    assert len(firsts) == 84 and [r["measure"] for r in firsts] == list(range(1, 85))
    assert len(rows) == 168  # two beats per 2/4 bar


def test_irregular_bars_keep_their_chords_durations(choro, pieces, built):
    rosa = built["1_rosa_WF"]
    assert rosa.irregular_bars[:3] == [10, 11, 16]
    bars = choro.read_bars(pieces["1_rosa_WF"].rows, choro.chord_times(pieces["1_rosa_WF"].rows))
    assert bars[10].start == bars[9].start + 2  # bar 10's chords add up to a half note, not a 3/4 bar
    assert bars[9].n_beats == 2


def test_keys_before_their_chords(built):
    rows = built["1_alvorada_WF"].csvs["harmony.csv"][1]
    assert rows[0]["harmony_or_key"] == "key" and rows[0]["symbol"] == "d"
    keys = [r for r in rows if r["harmony_or_key"] == "key"]
    assert [k["symbol"] for k in keys] == ["d", "D", "d", "D"]
    for i, r in enumerate(rows[1:], 1):
        if r["harmony_or_key"] == "key":
            assert rows[i + 1]["harmony_or_key"] == "harmony" and rows[i + 1]["time"] == r["time"]


def test_parts_and_phrases(built):
    rows = built["1_alvorada_WF"].csvs["form.csv"][1]
    parts = [(r["start"], r["end"], r["label"]) for r in rows if r["level"] == 2]
    assert parts == [("0.0", "4.0", "Intro"), ("4.0", "68.0", "A"), ("68.0", "134.0", "B")]
    phrases = [(r["start"], r["end"], r["label"]) for r in rows if r["level"] == 1]
    assert phrases[:5] == [("0.0", "4.0", "P0"), ("4.0", "8.0", "P0"), ("8.0", "30.0", "P1"),
                           ("30.0", "34.0", "P0"), ("34.0", "38.0", "P0")]  # bars 16-19: P0 twice
    assert phrases[-3:] == [("134.0", "138.0", "P0"), ("138.0", "160.0", "P1"), ("160.0", "168.0", "P2")]
    assert len(phrases) == 14


def test_the_rules_must_match_the_table(choro, pieces):
    piece = pieces["1_alvorada_WF"]
    broken = choro.Piece(piece.id, piece.rows, piece.transcription.replace("$P3 $P4 $P3", "$P3 $P3"))
    with pytest.raises(ValueError, match="don't match"):
        choro.form_units(broken, choro.chord_times(piece.rows))


def test_bass_from_the_transcribed_label(choro):
    assert choro.checked_harte("Eb7/Bb", "Eb:7/b5")[0] == "Eb:7/5"
    assert choro.checked_harte("C(#5)/G#", "C:aug/5")[0] == "C:aug/#5"
    assert choro.checked_harte("F#o/A", "F#:dim/3")[0] == "F#:dim/b3"
    assert choro.checked_harte("D/C", "D:maj/b7") == ("D:maj/b7", "")
    assert choro.checked_harte("NC", "N") == ("N", "")


def test_seventh_among_the_added_tones(choro):
    assert choro.checked_harte("Fm(7M)(9)", "F:min(7M,9)")[0] == "F:min(7,9)"
    assert choro.checked_harte("C7M", "C:maj7")[0] == "C:maj7"


def test_corrections_are_reported(built):
    assert any("Eb7/Bb" in p and "Eb:7/b5" in p for p in built["1_enigmatico_WF"].problems)


def test_triad_over_its_minor_seventh(choro):
    placed = choro.translate("D/C", "D:maj/b7", "G")
    assert (placed.symbol, placed.display_mode, placed.custom_text) == ("D7/C", "custom", "D/C")


def test_never_another_root(choro):
    placed = choro.translate("D7(b9)", "D:7(b9)", "g")
    assert (placed.symbol, placed.display_mode, placed.custom_text) == ("D7", "custom", "D7(b9)")
    assert "stored without its added tones" in placed.comments


def test_exact_chords_show_as_letters(choro):
    assert choro.translate("A7", "A:7", "d") == choro.Placed("A7", "letter")
    assert choro.translate("Cm6/Eb", "C:min6/b3", "d").symbol == "Cm6/Eb"


def test_every_chord_is_placed(built, pieces):
    for p, c in built.items():
        chords = [r for r in c.csvs["harmony.csv"][1] if r["harmony_or_key"] == "harmony"]
        assert len(chords) + len(c.csvs["chords-unparsed.csv"][1]) == c.source_rows["Harmony/chords"]
        assert c.source_rows["Harmony/chords"] == sum(1 for r in pieces[p].rows if r["harte"] != "N")
        assert all(r["custom_text"] for r in chords if r["display_mode"] == "custom")


def test_metadata(built):
    md = built["1_alvorada_WF"].metadata
    assert md["title"] == "Alvorada" and md["composer"] == "Jacob do Bandolim"
    assert md["composition year"] == "1955" and md["tonality"] == "Dm" and md["time signature"] == "2/4"
    assert md["licence"] == md["analysis license"] == "CC BY-NC-SA 4.0"
    assert md["analysis author"].startswith("Fabian C. Moss") and "10.1080/09298215.2020.1797109" in md["notes"]


def test_script_quotes_its_values(choro, built, tmp_path):
    script = choro.write_script(built["1_alvorada_WF"], tmp_path, tmp_path / "x.tla")
    assert 'metadata set "title" "Alvorada"' in script
    assert 'timelines import hierarchy by-time --target-name "Form"' in script
    assert script.rstrip().endswith("--overwrite")
