"""Fixtures: Dezrann's archive (md5-checked, cached) and DCML's converted files for the nine movements.

DEZRANN_TEST_DCML may name an existing output directory of dcml-mozart/convert.py (with ``tla/``);
otherwise the movements are converted into a temporary one.
"""
import importlib.util
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dezrann = _load("dezrann_convert", HERE / "convert.py")


@pytest.fixture(scope="session")
def dez():
    return dezrann


@pytest.fixture(scope="session")
def root(tmp_path_factory):
    """The unzipped analyses and measure maps of the nine movements."""
    return dezrann.extract(dezrann.fetch_archive(), dezrann.PIECES, tmp_path_factory.mktemp("dez"))


@pytest.fixture(scope="session")
def dcml_out(tilia, tmp_path_factory):
    env = os.environ.get("DEZRANN_TEST_DCML")
    if env and all((Path(env) / "tla" / f"{p}.tla").exists() for p in dezrann.PIECES):
        return Path(env)
    dcml = _load("dcml_convert", HERE.parent / "dcml-mozart" / "convert.py")
    out = tmp_path_factory.mktemp("dcml-out")
    dcml.convert(dezrann.PIECES, out, jobs=1)
    return out


@pytest.fixture(scope="session")
def merged(dcml_out, tmp_path_factory):
    out = tmp_path_factory.mktemp("dez-out")
    summary = dezrann.convert(dezrann.PIECES, dcml_out, out)
    return out, summary
