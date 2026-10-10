"""The merged files, through TiLiA."""
import json

import pytest


def timelines(path):
    data = json.loads(path.read_text())
    out = {}
    for t in data["timelines"].values():
        if t.get("name"):
            c = t.get("components", {})
            out[t["name"]] = (t["kind"], list(c.values()) if isinstance(c, dict) else list(c))
    return out


def test_k279_1_overlay(merged, dcml_out):
    out, summary = merged
    new, old = timelines(out / "tla" / "K279-1.tla"), timelines(dcml_out / "tla" / "K279-1.tla")
    structure = new["Structure (Dezrann)"][1]
    assert len(structure) == 9 and len(new["Texture (Dezrann)"][1]) == 100
    by_level = {lvl: sorted(c["label"] for c in structure if c["level"] == lvl) for lvl in (1, 2)}
    assert by_level[2] == ["Development", "Exposition", "Recapitulation"]
    assert by_level[1] == sorted(["First subject", "Second subject", "Transition"] * 2)
    exposition = next(c for c in structure if c["label"] == "Exposition")
    assert (exposition["start"], exposition["end"]) == (0.0, 150.5)
    assert new["Structure (Dezrann)"][0].lower().startswith("hier")
    for name, (kind, comps) in old.items():  # DCML's timelines are unchanged
        assert new[name][0] == kind
        assert sorted(json.dumps({k: v for k, v in c.items() if k != "hash"}, sort_keys=True) for c in comps) == \
            sorted(json.dumps({k: v for k, v in c.items() if k != "hash"}, sort_keys=True) for c in new[name][1]), name
    assert set(new) - set(old) == {"Structure (Dezrann)", "Texture (Dezrann)"}


def test_all_nine_counts_equal_dez_labels(merged, dez, root):
    out, summary = merged
    assert sorted(summary) == sorted(dez.PIECES)
    for piece, s in summary.items():
        labels = json.loads((root / "analysis" / f"{piece}_texture.dez").read_text(encoding="utf-8"))["labels"]
        for typ in ("Structure", "Texture"):
            n = sum(1 for lab in labels if lab["type"] == typ)
            assert s["components"][typ] == s["dez_labels"][typ] == n, (piece, typ)
        assert s["dcml_unchanged"], piece


def test_lint_finds_no_errors(merged):
    _, summary = merged
    for piece, s in summary.items():
        assert s["lint"]["errors"] == 0, (piece, s["lint"]["examples"])


def test_bar_numbers_agree_with_dcml(merged):
    _, summary = merged
    for piece, s in summary.items():
        assert s["bar_numbers"]["numbers_agree"] and s["bar_numbers"]["starts_agree"], piece


def test_originals_are_untouched(merged, dcml_out, dez):
    out, _ = merged
    for piece in dez.PIECES:
        assert (out / "work" / f"{piece}.tla").read_bytes() == (dcml_out / "tla" / f"{piece}.tla").read_bytes()
