"""Fixtures: the four fixture movements' tables, downloaded (md5-checked) into the cache."""
import importlib.util
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
