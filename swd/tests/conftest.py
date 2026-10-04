import csv
import json

import pytest

from swd import convert

ITEMS = ["Schubert_D911-01_HU33", "Schubert_D911-02_HU33"]


@pytest.fixture(scope="session")
def source():
    """Reads the fixtures' members of the SWD archive (single members unless the whole archive is cached)."""
    return convert.Source.open()


@pytest.fixture(scope="session")
def data(source):
    titles, keys = convert.song_titles(source), convert.global_keys(source)
    return {item: convert.read_item(source, item, titles, keys) for item in ITEMS}


@pytest.fixture(scope="session")
def written(data, tmp_path_factory):
    """item -> table name -> rows (list of dicts) of the CSVs the converter writes."""
    out = {}
    for item, d in data.items():
        folder = tmp_path_factory.mktemp(item)
        paths = convert.write_tables(convert.build_tables(d), folder)
        out[item] = {name: list(csv.DictReader(open(p, encoding="utf-8"))) for name, p in paths.items()}
    return out


@pytest.fixture(scope="session")
def converted(source, tmp_path_factory, tilia):
    """The fixtures run through TiLiA: (output folder, summary)."""
    out = tmp_path_factory.mktemp("swd-out")
    summary = convert.convert_all(source, out, ITEMS, log=lambda *_: None)
    return out, summary


def read_tla(path):
    data = json.loads(path.read_text())
    timelines = {t["name"]: t for t in data["timelines"].values() if "name" in t}
    return data, timelines


def components(timeline):
    c = timeline.get("components", {})
    return list(c.values()) if isinstance(c, dict) else c
