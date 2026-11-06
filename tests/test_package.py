import os
import zipfile

import pytest

from common.package import LICENCES, build_package


@pytest.fixture
def files(tmp_path):
    (tmp_path / "a.tla").write_text('{"x": 1}')
    (tmp_path / "b.tla").write_text('{"y": 2}')
    return [tmp_path / "b.tla", tmp_path / "a.tla"]


def test_contents(tmp_path, files):
    path = build_package("demo", files, "CC-BY-3.0", "Made from X.", out_dir=tmp_path / "out")
    assert path == tmp_path / "out" / "demo.zip"
    z = zipfile.ZipFile(path)
    assert z.namelist() == ["demo/LICENSE", "demo/NOTICE.md", "demo/a.tla", "demo/b.tla"]
    assert "https://creativecommons.org/licenses/by/3.0/" in z.read("demo/LICENSE").decode()
    assert z.read("demo/NOTICE.md").decode() == "Made from X."
    assert z.read("demo/a.tla") == b'{"x": 1}'


@pytest.mark.parametrize("spdx", sorted(LICENCES))
def test_licence_urls(tmp_path, files, spdx):
    path = build_package("p", files, spdx, "n", out_dir=tmp_path / "out")
    assert LICENCES[spdx][1] in zipfile.ZipFile(path).read("p/LICENSE").decode()


def test_odbl_url():
    assert LICENCES["ODbL-1.0"][1] == "https://opendatacommons.org/licenses/odbl/1-0/"


def test_deterministic(tmp_path, files):
    first = build_package("demo", files, "ODbL-1.0", "n", out_dir=tmp_path / "o1")
    for f in files:
        os.utime(f, (1_000_000_000, 1_000_000_000))
    second = build_package("demo", list(reversed(files)), "ODbL-1.0", "n", out_dir=tmp_path / "o2")
    assert first.read_bytes() == second.read_bytes()
    assert {i.date_time for i in zipfile.ZipFile(first).infolist()} == {(1980, 1, 1, 0, 0, 0)}


def test_unknown_licence(tmp_path, files):
    with pytest.raises(ValueError):
        build_package("demo", files, "NOT-A-LICENCE", "n", out_dir=tmp_path)
