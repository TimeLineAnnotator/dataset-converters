"""The fixtures through TiLiA: counts in the saved files equal the source rows."""
import json
import zipfile

import pytest

FIXTURES = ["K284-1", "K331-1", "K280-1", "K333-1"]


@pytest.fixture(scope="module")
def converted(dcml, files, tilia, tmp_path_factory):
    out = tmp_path_factory.mktemp("dcml-out")
    summary = dcml.convert(FIXTURES, out, files=files)
    return out, summary


def timelines(path):
    data = json.loads(path.read_text())
    return {t.get("name"): t for t in data["timelines"].values() if t.get("name")}, data


def test_counts_equal_source_rows(converted, movements):
    out, summary = converted
    assert sorted(summary) == sorted(FIXTURES)
    for p in FIXTURES:
        layers = {k: v for k, v in summary[p].items() if k != "lint"}
        assert list(layers) == ["Measures", "Harmony/keys", "Harmony/chords", "Cadences", "Phrases"]
        for layer, v in layers.items():
            assert v["components"] == v["source_rows"] == movements[p].source_rows[layer], (p, layer)
        assert json.loads((out / "summary.json").read_text()) == summary


def test_lint_finds_no_errors(converted):
    _, summary = converted
    for p in FIXTURES:
        assert summary[p]["lint"]["errors"] == 0, (p, summary[p]["lint"]["examples"])


def test_timelines_and_kinds(converted):
    out, _ = converted
    for p in FIXTURES:
        tl, _ = timelines(out / "tla" / f"{p}.tla")
        assert {n: t["kind"].lower() for n, t in tl.items() if n} == {
            "Measures": "beat", "Phrases": "hierarchy", "Harmony": "harmony",
            "Cadences": "marker", "Chords (unparsed)": "marker"}


def test_bar_numbers_and_metadata_in_the_saved_file(converted, tables):
    out, _ = converted
    for p in FIXTURES:
        tl, data = timelines(out / "tla" / f"{p}.tla")
        assert tl["Measures"]["measure_numbers"] == [int(r["mn"]) for r in tables[p][1]]
        md = data["media_metadata"]
        assert md["time unit"] == "quarter notes (no recording: one second stands for one quarter note)"
        assert md["licence"] == "CC BY-NC-SA 4.0" and md["composer"] == "Wolfgang Amadeus Mozart"
        assert data["media_path"] == ""


def test_chord_display_in_the_saved_file(converted, tilia_keeps_harmony_display):
    if not tilia_keeps_harmony_display:
        pytest.skip("this TiLiA drops the harmony CSV's display_mode and custom_text (TimeLineAnnotator/desktop#631)")
    out, _ = converted
    tl, _ = timelines(out / "tla" / "K331-1.tla")
    chords = [c for c in tl["Harmony"]["components"].values() if "quality" in c]
    assert any(c.get("display_mode") == "custom" and c.get("custom_text") == "V(64)" for c in chords)
    assert all(c["custom_text"] for c in chords if c.get("display_mode") == "custom")


def test_package(dcml, converted, tmp_path):
    out, _ = converted
    pkg = dcml.package(out, tmp_path)
    assert pkg.name == "dcml-mozart-v2.3-tilia.zip"
    z = zipfile.ZipFile(pkg)
    names = z.namelist()
    assert sorted(n.split("/")[-1] for n in names if n.endswith(".tla")) == sorted(f"{p}.tla" for p in FIXTURES)
    assert "dcml-mozart-v2.3-tilia/LICENSE" in names and "dcml-mozart-v2.3-tilia/NOTICE.md" in names
    assert "CC BY-NC-SA" in z.read("dcml-mozart-v2.3-tilia/LICENSE").decode() or "NonCommercial" in z.read(
        "dcml-mozart-v2.3-tilia/LICENSE").decode()
    for n in names:
        if n.endswith(".tla"):
            d = json.loads(z.read(n))
            assert d["file_path"] == "" and d["media_path"] == ""
