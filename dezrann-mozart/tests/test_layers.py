"""Dezrann's layers as rows, without TiLiA."""
import csv
import json
import zipfile
from collections import Counter

import pytest


def dez_counts(root, piece):
    labels = json.loads((root / "analysis" / f"{piece}_texture.dez").read_text(encoding="utf-8"))["labels"]
    return Counter(lab["type"] for lab in labels)


def test_k279_1_structure_and_texture(dez, root):
    layers = dez.layer_rows(piece := "K279-1", root)
    assert len(layers["Structure"]["times"]) == 9 and len(layers["Texture"]["times"]) == 100
    assert dez_counts(root, piece)["Positive Feedback"] == 25  # left out
    levels = {(r["label"], r["start"]): r["level"] for r in layers["Structure"]["times"]}
    assert levels[("Exposition", 0.0)] == levels[("Development", 152.0)] == levels[("Recapitulation", 228.0)] == 2
    assert levels[("First subject", 0.0)] == levels[("Second subject", 64.0)] == 1
    assert sum(1 for v in levels.values() if v == 2) == 3 and sum(1 for v in levels.values() if v == 1) == 6
    # quarter-second times
    assert {(r["start"], r["end"]) for r in layers["Structure"]["times"] if r["label"] == "Exposition"} == {(0.0, 150.5)}
    assert {r["level"] for r in layers["Texture"]["times"]} == {1}


def test_bars_and_times_describe_the_same_labels(dez, root):
    layers = dez.layer_rows("K279-1", root)
    for typ, v in layers.items():
        assert [r["label"] for r in v["bars"]] == [r["label"] for r in v["times"]]
        assert [r["level"] for r in v["bars"]] == [r["level"] for r in v["times"]]
        assert list(v["bars"][0]) == dez.BAR_FIELDS


@pytest.mark.parametrize("piece", ["K279-1", "K279-2", "K279-3", "K280-1", "K280-2", "K280-3", "K283-1", "K283-2", "K283-3"])
def test_counts_equal_dez_labels(dez, root, piece):
    layers = dez.layer_rows(piece, root)
    counts = dez_counts(root, piece)
    assert len(layers["Structure"]["bars"]) == counts["Structure"] > 0
    assert len(layers["Texture"]["bars"]) == counts["Texture"] > 0
    last = max(r["end"] for v in layers.values() for r in v["times"])
    assert all(0 <= r["start"] < r["end"] <= last for v in layers.values() for r in v["times"])


def test_script_commands(dez, tmp_path):
    lines = dez.write_script(tmp_path / "a.tla", tmp_path / "b.tla", tmp_path / "s.csv", tmp_path / "t.csv").splitlines()
    assert lines[0] == f"open {tmp_path / 'a.tla'}"
    assert lines[1] == 'timelines add hierarchy --name "Structure (Dezrann)"'
    assert lines[2] == 'timelines add hierarchy --name "Texture (Dezrann)"'
    assert lines[3].startswith('timelines import hierarchy by-time --target-name "Structure (Dezrann)" --file ')
    assert lines[4].startswith('timelines import hierarchy by-time --target-name "Texture (Dezrann)" --file ')
    assert lines[5] == f"save {tmp_path / 'b.tla'} --overwrite"


def test_package_holds_only_dezrann_layers(dez, root, tmp_path):
    for piece in dez.PIECES:
        layers = dez.layer_rows(piece, root)
        (tmp_path / "csv-by-bar").mkdir(exist_ok=True)
        for typ, (_, stem) in dez.LAYERS.items():
            dez.write_csv(tmp_path / "csv-by-bar" / f"{piece}-{stem}.csv", dez.BAR_FIELDS, layers[typ]["bars"])
    z = zipfile.ZipFile(dez.package(tmp_path, tmp_path / "package"))
    names = z.namelist()
    assert len([n for n in names if n.endswith(".csv")]) == 18 and not [n for n in names if n.endswith(".tla")]
    assert "opendatacommons.org/licenses/odbl" in z.read(f"{dez.PACKAGE_NAME}/LICENSE").decode()
    notice = z.read(f"{dez.PACKAGE_NAME}/NOTICE.md").decode()
    for needle in ("Couturier", "Bigo", "Hentschel", "Levé", "Neuwirth", "Rohrmeier", "10.57745/OHRWPC",
                   "Positive Feedback", "Local Key"):
        assert needle in notice
    rows = list(csv.DictReader(z.read(f"{dez.PACKAGE_NAME}/K279-1-structure.csv").decode().splitlines()))
    assert list(rows[0]) == dez.BAR_FIELDS and len(rows) == 9
