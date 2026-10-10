"""The fixtures through TiLiA: counts in the saved files equal the source rows."""
import json
import zipfile

import pytest

FIXTURES = ["1_alvorada_WF", "1_rosa_WF", "1_enigmatico_WF"]


@pytest.fixture(scope="module")
def converted(choro, pieces, tilia, tmp_path_factory):
    out = tmp_path_factory.mktemp("choro-out")
    summary = choro.convert(FIXTURES, out, pieces=pieces)
    return out, summary


def timelines(path):
    data = json.loads(path.read_text())
    return {t.get("name"): t for t in data["timelines"].values() if t.get("name")}, data


def test_counts_equal_source_rows(converted, built):
    out, summary = converted
    assert list(summary) == FIXTURES
    for p in FIXTURES:
        assert list(summary[p]) == ["Measures", "Harmony/keys", "Harmony/chords", "Parts", "Phrases"]
        for layer, v in summary[p].items():
            assert v["components"] == v["source_rows"] == built[p].source_rows[layer], (p, layer)
    report = json.loads((out / "source-report.json").read_text())
    assert report["1_rosa_WF"]["irregular_bars"][:3] == [10, 11, 16]


def test_timelines_and_kinds(converted):
    out, _ = converted
    for p in FIXTURES:
        tl, _ = timelines(out / "tla" / f"{p}.tla")
        assert {n: t["kind"].lower() for n, t in tl.items()} == {
            "Measures": "beat", "Form": "hierarchy", "Harmony": "harmony", "Chords (unparsed)": "marker"}


def test_bar_numbers_and_metadata_in_the_saved_file(converted):
    out, _ = converted
    tl, data = timelines(out / "tla" / "1_alvorada_WF.tla")
    assert tl["Measures"]["measure_numbers"] == list(range(1, 85))
    md = data["media_metadata"]
    assert md["time unit"] == "quarter notes (no recording: one second stands for one quarter note)"
    assert md["licence"] == "CC BY-NC-SA 4.0" and md["composer"] == "Jacob do Bandolim"
    assert md["composition year"] == "1955" and data["media_path"] == ""


def test_chord_display_in_the_saved_file(converted, tilia_keeps_harmony_display):
    if not tilia_keeps_harmony_display:
        pytest.skip("this TiLiA drops the harmony CSV's display_mode and custom_text (TimeLineAnnotator/desktop#631)")
    out, _ = converted
    tl, _ = timelines(out / "tla" / "1_rosa_WF.tla")
    chords = [c for c in tl["Harmony"]["components"].values() if "quality" in c]
    assert any(c.get("display_mode") == "custom" and c.get("custom_text") == "D/C" and c["inversion"] == 3
               for c in chords)


def test_package(choro, converted, tmp_path):
    out, _ = converted
    pkg = choro.package(out, tmp_path)
    assert pkg.name == "choro-v1.3.3-tilia.zip"
    z = zipfile.ZipFile(pkg)
    names = z.namelist()
    assert sorted(n.split("/")[-1] for n in names if n.endswith(".tla")) == sorted(f"{p}.tla" for p in FIXTURES)
    assert "NonCommercial" in z.read("choro-v1.3.3-tilia/LICENSE").decode()
    assert "Moss, F. C." in z.read("choro-v1.3.3-tilia/NOTICE.md").decode()
    for n in names:
        if n.endswith(".tla"):
            d = json.loads(z.read(n))
            assert d["file_path"] == "" and d["media_path"] == ""
