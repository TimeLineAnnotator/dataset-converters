"""Fixtures: the four fixture movements' tables, downloaded (md5-checked) into the cache."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("dcml_convert", Path(__file__).resolve().parents[1] / "convert.py")
convert = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convert)

FIXTURES = ["K284-1", "K331-1", "K280-1", "K333-1"]


@pytest.fixture(scope="session")
def dcml():
    return convert


@pytest.fixture(scope="session")
def files():
    return convert.fetch_sources(FIXTURES)


@pytest.fixture(scope="session")
def tables(files):
    """piece -> (harmonies, measures) as lists of dicts."""
    return {p: (convert.read_tsv(files[f"harmonies/{p}.harmonies.tsv"]),
                convert.read_tsv(files[f"measures/{p}.measures.tsv"])) for p in FIXTURES}


@pytest.fixture(scope="session")
def movements(files, tables):
    meta = convert.read_metadata(files["metadata.tsv"])
    return {p: convert.build_movement(p, h, m, meta[p]) for p, (h, m) in tables.items()}


@pytest.fixture(scope="session")
def tilia_keeps_harmony_display(tilia, tmp_path_factory):
    """Whether this TiLiA's harmony CSV import keeps display_mode and custom_text.

    Releases up to 0.7.0 parse those columns and drop them; TimeLineAnnotator/desktop#631 fixes that.
    """
    from common.runner import run_script

    d = tmp_path_factory.mktemp("display-probe")
    (d / "h.csv").write_text("harmony_or_key,time,symbol,display_mode,custom_text\nharmony,0,C,custom,probe\n")
    (d / "s.txt").write_text(
        "metadata set-media-length 4\ntimelines add harmony --name H\n"
        f"timelines import harmony by-time --target-name H --file {d / 'h.csv'}\nsave {d / 'p.tla'} --overwrite\n")
    run_script(d / "s.txt", tilia=tilia)
    data = json.loads((d / "p.tla").read_text())
    return any(c.get("custom_text") == "probe" for t in data["timelines"].values() if t.get("name") == "H"
               for c in t["components"].values())
