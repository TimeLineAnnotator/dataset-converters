"""Fixtures: the corpus's zip, downloaded (md5-checked) into the cache, and three of its pieces."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("choro_convert", Path(__file__).resolve().parents[1] / "convert.py")
convert = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convert)

# a part with an Intro and a phrase played twice in a row; bars that don't fill 3/4 and triads over their
# minor seventh; a slash chord whose Harte label has another bass
FIXTURES = ["1_alvorada_WF", "1_rosa_WF", "1_enigmatico_WF"]


@pytest.fixture(scope="session")
def choro():
    return convert


@pytest.fixture(scope="session")
def pieces():
    return convert.read_corpus(convert.fetch_corpus())


@pytest.fixture(scope="session")
def built(pieces):
    return {p: convert.build_piece(pieces[p]) for p in FIXTURES}
