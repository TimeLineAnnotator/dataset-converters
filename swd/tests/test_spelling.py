import music21
import pytest

from swd import convert, spelling

GEFRORNE_OL06 = "Schubert_D911-03_OL06"  # E-flat minor; SWD names it D-sharp minor
GEFRORNE_HU33 = "Schubert_D911-03_HU33"  # D minor
WASSERFLUT_HU33 = "Schubert_D911-06_HU33"  # D minor; annotators 2 and 3 have it in C and A-sharp minor
MUT_SC06 = "Schubert_D911-22_SC06"


@pytest.fixture(scope="module")
def items(source):
    return {i: convert.read_item(source, i) for i in (GEFRORNE_OL06, GEFRORNE_HU33, WASSERFLUT_HU33, MUT_SC06)}


@pytest.fixture(scope="module")
def harmony(items):
    return {i: convert.build_tables(d)["harmony"][1] for i, d in items.items()}


def numeral_accidental(symbol, key):
    """Accidental in front of a chord's Roman numeral, in semitones: its root against the key's note of that letter."""
    root = music21.pitch.Pitch(symbol[0] + "".join(c for c in symbol[1:3] if c in "#b").replace("b", "-"))
    k = music21.key.Key(key)
    return int(root.alter - next(p.alter for p in k.pitches if p.step == root.step))


def chords_with_keys(rows):
    key = None
    for kind, time, symbol, *_ in rows:
        if kind == "key":
            key = symbol
        else:
            yield time, symbol, key


# ---------------------------------------------------------------- the parts
def test_a_label_without_quality_is_major_and_n_is_none():
    assert spelling.parse("D#/G") == ("D#", "maj", "G")
    assert spelling.parse("Db:(3,#5,7)/C") == ("Db", "(3,#5,7)", "C")
    assert spelling.parse("N") is None and spelling.parse("X") is None


def test_the_shift_is_the_one_that_makes_the_chords_equal():
    score = [spelling.parse(l) for l in ("F:min", "Db:maj", "Eb:7/G")]
    performance = [spelling.parse(l) for l in ("D#:min", "B:maj", "C#:7/F")]
    assert spelling.chord_shift(score, performance, "x") == 10


def test_chords_that_are_not_the_score_transposed_are_refused():
    score = [spelling.parse(l) for l in ("F:min", "Db:maj")]
    with pytest.raises(ValueError, match="x: the performance's chords are not the score's, transposed"):
        spelling.chord_shift(score, [spelling.parse(l) for l in ("D#:min", "C:maj")], "x")
    with pytest.raises(ValueError):
        spelling.chord_shift(score, score[:1], "x")
    with pytest.raises(ValueError):  # no chords: every shift fits, so none says how to spell
        spelling.chord_shift([None], [None], "x")


def test_the_transposition_writes_the_fewest_accidentals():
    score = [spelling.parse(l) for l in ("F:min", "Db:maj", "Bb:min", "Eb:7/G", "Ab:maj")]
    down_a_step = spelling.transposition(score, 10)
    assert down_a_step.name == "m7"  # up a minor seventh: E-flat minor, not D-sharp minor (an augmented sixth)
    assert spelling.respell(score[3], down_a_step) == "Db:7/F"
    assert spelling.respell(score[0], down_a_step) == "Eb:min"


def test_keys_moved_apart_from_the_chords_are_found():
    chords = [(0.0, ("D", "min", None)), (1.0, ("A", "7", None)), (2.0, ("D", "min", None)), (3.0, ("F", "maj", None))]
    keys = [{"start": "0", "end": "2.5", "key": "D:min"}, {"start": "2.5", "end": "4", "key": "F:maj"}]
    assert spelling.key_offset(keys, chords) == 0
    lowered = [dict(k, key=k["key"].replace("D:", "C:").replace("F:", "D#:")) for k in keys]
    assert spelling.key_offset(lowered, chords) == 2


def test_a_key_is_named_as_the_chords_name_its_tonic_within_seven_accidentals():
    assert spelling.key_label(3, "min", {3: "Eb"}) == "Eb:min"
    assert spelling.key_label(3, "min", {3: "D#"}) == "D#:min"
    assert spelling.key_label(6, "min", {6: "Gb"}) == "F#:min"  # G-flat minor would have nine flats
    assert spelling.key_label(10, "maj", {}) == "Bb:maj"


def test_a_key_written_enharmonically_moves_its_chords():
    move = spelling.enharmonic_shift("F#:min", {6: "Gb"})
    assert spelling.respell(("Db", "7", None), move) == "C#:7"
    assert spelling.enharmonic_shift("Eb:min", {3: "Eb"}) is None


def test_the_global_key_fills_the_gaps_of_annotator_1s_keys():
    data = {"chord": [{"start": t, "shorthand": "C:maj"} for t in ("0", "1", "2", "3", "4")]}
    keys = [{"start": "0", "end": "1.5", "key": "C:maj"}, {"start": "3", "end": "5", "key": "G:maj"}]
    assert convert.key_rows(data, keys, "F:maj") == [("0", "C:maj"), ("2", "F:maj"), ("3", "G:maj")]


# ---------------------------------------------------------------- the songs
def test_gefrorne_traenen_is_spelled_from_the_score(items, harmony):
    rows = harmony[GEFRORNE_OL06]
    assert rows[0][:3] == ["key", "2.02", "e-"]
    assert convert.respelled(items[GEFRORNE_OL06])["globalkey"] == "Eb:min"
    # bar 53: SWD's C#:7/F, the score's Eb:7/G a step down
    assert next(r for r in rows if r[1] == "148.64")[2:4] == ["Db7/F", "roman"]
    # bar 29, in G-flat major: SWD's G:dim/C#, the score's A:dim/Eb
    assert next(r[2] for r in rows if r[1] == "83.98" and r[0] == "harmony") == "Gdim/Db"


def test_a_passage_in_g_flat_minor_is_written_in_f_sharp_minor(harmony):
    rows = harmony[GEFRORNE_OL06]
    assert ["key", "69.08", "f#", "letter", "", ""] in rows
    assert [r[2] for r in rows if r[0] == "harmony" and 69 <= float(r[1]) < 78] == ["G#7", "C#", "C#", "B#o7"]


def test_no_numeral_has_a_double_accidental(harmony):
    for item, rows in harmony.items():
        worst = max(abs(numeral_accidental(s, k)) for _, s, k in chords_with_keys(rows))
        assert worst <= 1, item


def test_numerals_that_were_sharp_for_flat_are_plain(harmony):
    # D minor and F major: SWD's A# (bars 52 and 53) is B-flat, and its D# is E-flat
    rows = harmony[GEFRORNE_HU33]
    assert [r[2] for r in rows if r[1] in ("134.06", "135.32", "139.72")] == ["Bb", "Bb+M7/A", "Bb"]
    assert not [s for _, s, k in chords_with_keys(rows) if s.startswith(("A#", "D#")) and k in ("d", "F")]


def test_annotators_keys_are_moved_to_the_chords(items):
    for item in (WASSERFLUT_HU33, MUT_SC06):
        spelled = convert.respelled(items[item])
        assert spelled["offsets"] == {1: 0, 2: 2, 3: 4}
        firsts = {n: spelled["localkey"][n][0]["key"] for n in (1, 2, 3)}
        assert len(set(firsts.values())) == 1, (item, firsts)
    assert convert.respelled(items[GEFRORNE_OL06])["offsets"] == {1: 0, 2: 0, 3: 0}
