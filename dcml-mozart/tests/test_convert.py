"""Unit tests of the CSVs and scripts (no TiLiA needed)."""
from fractions import Fraction

import pytest


FIXTURES = ["K284-1", "K331-1", "K280-1", "K333-1"]


def rows(movement, name):
    return movement.csvs[name][1]


def test_the_item_list_holds_the_54_movements(dcml):
    assert len(dcml.PIECES) == 54 and len(set(dcml.PIECES)) == 54
    assert all(p in dcml.PIECES for p in FIXTURES)
    assert all(f"harmonies/{p}.harmonies.tsv" in dcml.MD5S and f"measures/{p}.measures.tsv" in dcml.MD5S
               for p in dcml.PIECES)


# ------------------------------------------------------------------ measures
def test_beats_per_bar_follow_each_bars_time_signature(movements, tables):
    """K331-1 is in 6/8 (six eighth-note beats in 3 s), then 4/4 from bar 109 (four beats)."""
    beats = rows(movements["K331-1"], "measures.csv")
    per_bar = {}
    for b in beats:
        per_bar.setdefault((b["measure"], b["time"] if b["is_first_in_measure"] == "true" else None), 0)
    firsts = [i for i, b in enumerate(beats) if b["is_first_in_measure"] == "true"]
    counts = [b - a for a, b in zip(firsts, firsts[1:] + [len(beats)])]
    measures = tables["K331-1"][1]
    assert len(counts) == len(measures)
    for r, n in zip(measures, counts):
        num = int(r["timesig"].split("/")[0])
        nominal = Fraction(4 * num, int(r["timesig"].split("/")[1]))
        assert n == max(1, round(num * 4 * Fraction(r["act_dur"]) / nominal))
    assert counts[0] == 6 and counts[-1] == 4
    assert [b["time"] for b in beats[:3]] == ["0.0", "0.5", "1.0"]  # eighth notes: half a second


def test_other_time_signatures(movements):
    assert rows(movements["K280-1"], "measures.csv")[:4] == [
        {"time": "0.0", "measure": 1, "is_first_in_measure": "true"},
        {"time": "1.0", "measure": 1, "is_first_in_measure": "false"},
        {"time": "2.0", "measure": 1, "is_first_in_measure": "false"},
        {"time": "3.0", "measure": 2, "is_first_in_measure": "true"},
    ]


def test_pickup_bar_is_bar_zero_with_one_beat(movements):
    beats = rows(movements["K333-1"], "measures.csv")
    assert beats[0] == {"time": "0.0", "measure": 0, "is_first_in_measure": "true"}
    assert beats[1] == {"time": "1.0", "measure": 1, "is_first_in_measure": "true"}


def test_bar_starts_come_from_the_quarterbeat_columns(dcml, tables):
    """K331-1 has voltas, so its table has _all_endings; K284-1's has not."""
    h, m = tables["K331-1"]
    assert "quarterbeats_all_endings" in m[0]
    bars = dcml.read_bars(m)
    assert [b.start for b in bars] == [Fraction(r["quarterbeats_all_endings"]) for r in m]
    assert [b.mn for b in bars[96:100]] == [97, 98, 98, 99]  # first and second ending of bar 98
    assert bars[98].start == 294 and bars[97].start == 291
    h, m = tables["K284-1"]
    assert "quarterbeats_all_endings" not in m[0]
    assert [b.start for b in dcml.read_bars(m)] == [Fraction(r["quarterbeats"]) for r in m]


def test_beat_times_ascend_and_the_media_length_is_the_end_of_the_last_bar(movements, tables):
    for p in FIXTURES:
        times = [float(b["time"]) for b in rows(movements[p], "measures.csv")]
        assert times == sorted(set(times))
        last = tables[p][1][-1]
        col = "quarterbeats_all_endings" if "quarterbeats_all_endings" in last else "quarterbeats"
        assert movements[p].media_length == Fraction(last[col]) + Fraction(last["duration_qb"])


def test_fractional_quarterbeats_give_exact_times(movements, tables):
    h = tables["K331-1"][0]
    assert any("/" in r["quarterbeats_all_endings"] for r in h)
    times = {float(r["time"]) for r in rows(movements["K331-1"], "harmony.csv")}
    assert 10.5 in times and 46.5 in times


# ------------------------------------------------------------------ keys
def test_relative_local_keys_become_absolute(movements):
    def keys(p):
        return [(r["time"], r["symbol"]) for r in rows(movements[p], "harmony.csv") if r["harmony_or_key"] == "key"]

    # K284-1 is in D: V is A, vi is b, ...
    assert keys("K284-1") == [("0.0", "D"), ("84.0", "A"), ("204.0", "a"), ("209.0", "e"), ("225.0", "b"),
                              ("245.0", "D")]
    assert keys("K280-1")[:3] == [("0.0", "F"), ("78.0", "C"), ("198.0", "d")]


def test_a_key_row_comes_before_the_chords_it_governs(movements):
    for m in movements.values():
        seen_key = False
        for r in rows(m, "harmony.csv"):
            seen_key |= r["harmony_or_key"] == "key"
            assert seen_key
        times = [float(r["time"]) for r in rows(m, "harmony.csv")]
        assert times == sorted(times)


# ------------------------------------------------------------------ chords, cadences, phrases
def test_chords_are_placed_as_format_converters_reports_them(dcml, tables, movements):
    from format_converters.harmony import translate_chord, translate_key

    for p in FIXTURES:
        harmonies = tables[p][0]
        expected, unparsed = [], []
        for r in harmonies:
            if r["chord"] in ("", "@none"):
                continue
            key = translate_key(r["localkey"], "dcml", globalkey=r["globalkey"])
            res = translate_chord(r["chord"], "dcml", key, dcml.dcml_truth(r))
            t = repr(float(dcml.label_time(r)))
            if res.outcome == "none":
                unparsed.append((t, r["chord"], res.comments))
            else:
                expected.append((t, res.symbol, res.display_mode, res.custom_text, res.comments))
        got = [(r["time"], r["symbol"], r["display_mode"], r["custom_text"], r["comments"])
               for r in rows(movements[p], "harmony.csv") if r["harmony_or_key"] == "harmony"]
        assert got == expected
        assert [(r["time"], r["label"], r["comments"]) for r in rows(movements[p], "chords-unparsed.csv")] == unparsed
        assert all(r["display_mode"] in ("letter", "roman", "custom") for r in rows(movements[p], "harmony.csv"))
        assert all(r["custom_text"] for r in rows(movements[p], "harmony.csv") if r["display_mode"] == "custom"
                   and r["harmony_or_key"] == "harmony")


def test_known_chords(movements):
    first = [r for r in rows(movements["K284-1"], "harmony.csv") if r["harmony_or_key"] == "harmony"][0]
    assert (first["time"], first["symbol"], first["display_mode"]) == ("0.0", "I", "roman")
    v64 = [r for r in rows(movements["K331-1"], "harmony.csv") if r["time"] == "10.5"][0]
    assert (v64["symbol"], v64["display_mode"], v64["custom_text"]) == ("V", "custom", "V(64)")
    assert "stored as their function V" in v64["comments"]


def test_rows_without_a_chord_are_not_placed(tables, movements):
    for p in FIXTURES:
        n = sum(1 for r in tables[p][0] if r["chord"] not in ("", "@none"))
        placed = sum(1 for r in rows(movements[p], "harmony.csv") if r["harmony_or_key"] == "harmony")
        assert placed + len(rows(movements[p], "chords-unparsed.csv")) == n


def test_cadences_are_markers_at_their_rows(movements, tables):
    assert [(r["time"], r["label"]) for r in rows(movements["K284-1"], "cadences.csv")][:4] == [
        ("64.0", "HC"), ("132.0", "HC"), ("160.0", "EC"), ("172.0", "PAC")]
    for p in FIXTURES:
        assert len(rows(movements[p], "cadences.csv")) == sum(1 for r in tables[p][0] if r["cadence"])


def test_phrases_from_the_phraseend_column(movements):
    assert rows(movements["K284-1"], "phrases.csv")[:4] == [
        {"start": "0.0", "end": "32.0", "level": 1, "label": "", "comments": ""},
        {"start": "32.0", "end": "64.0", "level": 1, "label": "", "comments": ""},
        {"start": "64.0", "end": "80.0", "level": 1, "label": "", "comments": ""},
        {"start": "84.0", "end": "132.0", "level": 1, "label": "", "comments": ""},
    ]


def _h(*marks):
    return [{"phraseend": m, "quarterbeats_all_endings": str(t), "quarterbeats": str(t)} for t, m in marks]


@pytest.mark.parametrize("marks,end,spans", [
    ([(0, "{"), (4, "}")], 10, [(0, 4)]),
    ([(0, "{"), (4, "}{"), (8, "}")], 10, [(0, 4), (4, 8)]),
    ([(0, "{"), (4, "}"), (6, "}")], 10, [(0, 4), (4, 6)]),  # a "}" with nothing open starts where the last ended
    ([(3, "}")], 10, [(0, 3)]),  # ... or at the piece's start
    ([(2, "}{"), (5, "}")], 10, [(0, 2), (2, 5)]),
    ([(0, "{"), (4, "}"), (6, "{")], 10, [(0, 4), (6, 10)]),  # open at the end closes at the end
    ([(0, "{"), (2, "{"), (4, "}")], 10, [(2, 4)]),  # a second "{" restarts the phrase
])
def test_phrase_rules(dcml, marks, end, spans):
    assert dcml.phrase_spans(_h(*marks), Fraction(end)) == [(Fraction(a), Fraction(b)) for a, b in spans]


# ------------------------------------------------------------------ scripts and metadata
def test_source_rows(movements, tables):
    for p in FIXTURES:
        h, m = tables[p]
        s = movements[p].source_rows
        assert s["Measures"] == len(m)
        assert s["Harmony/chords"] == sum(1 for r in h if r["chord"] not in ("", "@none"))
        assert s["Harmony/keys"] == len(rows(movements[p], "harmony.csv")) - s["Harmony/chords"] + len(
            rows(movements[p], "chords-unparsed.csv"))


def test_metadata(movements):
    md = movements["K331-1"].metadata
    assert md["title"] == "Piano Sonata no. 11 in A major, K. 331, movement 1: Andante grazioso"
    assert md["composer"] == "Wolfgang Amadeus Mozart"
    assert md["licence"] == "CC BY-NC-SA 4.0"
    assert md["time unit"] == "quarter notes (no recording: one second stands for one quarter note)"
    assert "10.5281/zenodo.7424962" in md["corpus"] and "v2.3" in md["corpus"]
    for part in ("Hentschel", "Neuwirth", "Rohrmeier", "Annotated by Uli Kneisel.",
                 "Reviewed by Johannes Hentschel, Markus Neuwirth."):
        assert part in md["notes"]
    assert all('"' not in v for v in md.values())


def test_script(dcml, movements, tmp_path):
    script = dcml.write_script(movements["K333-1"], tmp_path / "csv", tmp_path / "x.tla")
    lines = script.splitlines()
    assert lines[0].startswith('metadata set "title" "Piano Sonata no. 13')
    assert 'metadata set-media-length 660.0' in lines
    assert 'timelines add harmony --name "Harmony"' in lines
    assert f'timelines import harmony by-time --target-name "Harmony" --file {tmp_path / "csv" / "harmony.csv"}' in lines
    assert not any("by-measure" in line for line in lines)
    assert not any("Chords (unparsed)" in line and "import" in line for line in lines)  # nothing to import
    assert lines[-1] == f"save {tmp_path / 'x.tla'} --overwrite"


def test_no_tilia_writes_csvs_and_scripts_only(dcml, files, tmp_path):
    dcml.convert(["K280-1"], tmp_path, files=files, run_tilia=False)
    assert sorted(p.name for p in (tmp_path / "csv" / "K280-1").iterdir()) == [
        "cadences.csv", "chords-unparsed.csv", "harmony.csv", "measures.csv", "phrases.csv"]
    assert (tmp_path / "scripts" / "K280-1.txt").exists()
    assert not list((tmp_path / "tla").glob("*.tla"))
