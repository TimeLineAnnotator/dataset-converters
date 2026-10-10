import csv
import json

import pytest

from common import lint

C, D, E, F, G, A, B = range(7)


def mode(time, step, accidental=0, minor=False):
    return {"kind": "MODE", "time": time, "step": step, "accidental": accidental,
            "type": "minor" if minor else "major", "level": 2}


def chord(time, step, accidental=0, display="roman", applied_to=0):
    return {"kind": "HARMONY", "time": time, "step": step, "accidental": accidental, "quality": "major",
            "inversion": 0, "applied_to": applied_to, "display_mode": display, "level": 1}


def section(start, end, level=1, label=""):
    return {"kind": "HIERARCHY", "start": start, "end": end, "level": level, "label": label}


def tla(tmp_path, harmony=(), hierarchy=()):
    timelines = {"1": {"kind": "Harmony", "name": "Harmony", "components": dict(enumerate(harmony))},
                 "2": {"kind": "Hierarchy", "name": "Structure", "components": dict(enumerate(hierarchy))}}
    path = tmp_path / "x.tla"
    path.write_text(json.dumps({"timelines": timelines}))
    return path


def harmony_csv(tmp_path, rows):
    path = tmp_path / "harmony.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["harmony_or_key", "time", "symbol", "display_mode", "custom_text", "comments"])
        w.writerows(rows)
    return path


def rules(tmp_path, harmony=(), hierarchy=(), csv_rows=None):
    csvs = [harmony_csv(tmp_path, csv_rows)] if csv_rows is not None else []
    return lint.lint(tla(tmp_path, harmony, hierarchy), csvs)["rules"]


# ---------------------------------------------------------------- keys and roots
def test_a_root_two_semitones_from_the_key_is_an_error(tmp_path):
    # A-sharp in C minor is two semitones above the key's A-flat: ##VI for VII
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, A, 1)]) == {"numeral-double-accidental": 1}
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, B, -1)]) == {}


def test_a_key_past_seven_accidentals_is_an_error(tmp_path):
    assert rules(tmp_path, [mode(0, D, 1)]) == {"key-signature": 1}  # D-sharp major: nine sharps
    assert rules(tmp_path, [mode(0, C, 1)]) == {}  # C-sharp major: seven


def test_a_root_that_another_letter_fits_is_a_warning(tmp_path):
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, D, 1)]) == {"root-fits-respelled": 1}  # E-flat
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, D, -1)]) == {}  # D-flat, bII: C-sharp fits no better
    assert lint.LEVELS["root-fits-respelled"] == "warning"


def test_roots_are_read_against_the_key_in_force(tmp_path):
    # D-sharp is III in B major, and E-flat would not be better there
    assert rules(tmp_path, [mode(0, C, minor=True), chord(2, D, 1), mode(2, B)]) == {}  # a key comes before a chord at its time
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, D, 1), mode(2, B)]) == {"root-fits-respelled": 1}


def test_custom_applied_and_keyless_chords_are_skipped(tmp_path):
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, A, 1, display="custom")]) == {}
    assert rules(tmp_path, [mode(0, C, minor=True), chord(1, A, 1, applied_to=4)]) == {}
    assert rules(tmp_path, [chord(0, A, 1), mode(1, C, minor=True)]) == {}


# ---------------------------------------------------------------- slash basses
@pytest.mark.parametrize("symbol, rule", [
    ("C#7/E#", None),  # the third
    ("Bb7/D", None),
    ("Gdim/Db", None),
    ("C#7/F", "bass-enharmonic"),  # F is E-sharp
    ("Ebdim/A", "bass-enharmonic"),  # A is B-double-flat
    ("C/D", "bass-not-chord-tone"),
    ("V7/V", None),  # a Roman numeral: the slash is an applied chord
    ("Am", None),
])
def test_a_bass_is_a_chord_tone_under_its_own_name(symbol, rule):
    assert lint.bass_rule(symbol) == rule


def test_bass_levels():
    assert lint.LEVELS["bass-enharmonic"] == "error"
    assert lint.LEVELS["bass-not-chord-tone"] == "warning"


def test_basses_are_read_from_the_harmony_csv_without_its_custom_rows(tmp_path):
    rows = [["key", "0", "c#", "letter", "", ""], ["harmony", "1", "C#7/F", "letter", "", ""],
            ["harmony", "2", "C/D", "roman", "", ""], ["harmony", "3", "Co7/A", "custom", "C:dim7/A", ""]]
    assert rules(tmp_path, csv_rows=rows) == {"bass-enharmonic": 1, "bass-not-chord-tone": 1}


# ---------------------------------------------------------------- sections
def test_sections_that_overlap_at_one_level_are_an_error(tmp_path):
    assert rules(tmp_path, hierarchy=[section(0, 10), section(9, 20)]) == {"section-overlap": 1}
    assert rules(tmp_path, hierarchy=[section(0, 10), section(10, 20)]) == {}
    assert rules(tmp_path, hierarchy=[section(0, 10.001), section(10, 20)]) == {}  # rounding
    assert rules(tmp_path, hierarchy=[section(0, 20, level=2), section(0, 10), section(10, 20)]) == {}


# ---------------------------------------------------------------- the report
def test_the_report_counts_levels_and_keeps_the_first_examples(tmp_path):
    harmony = [mode(0, C, minor=True)] + [chord(t, A, 1) for t in range(1, 8)] + [chord(9, D, 1)]
    report = lint.lint(tla(tmp_path, harmony))
    assert (report["errors"], report["warnings"]) == (7, 1)
    assert report["rules"] == {"numeral-double-accidental": 7, "root-fits-respelled": 1}
    assert len(report["examples"]) == lint.EXAMPLES
    assert report["examples"][0] == {"rule": "numeral-double-accidental", "level": "error", "where": "Harmony",
                                     "time": 1, "what": "A# in c minor"}
