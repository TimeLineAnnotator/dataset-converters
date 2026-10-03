import hashlib
import urllib.request

import pytest

from common.download import ChecksumError, fetch, fetch_member
from conftest import BPSD_MEMBERS, BPSD_ROOT, BPSD_ZIP, DCML_BASE, DCML_FILES

URL = DCML_BASE + "measures/K279-1.tsv"
MD5 = DCML_FILES["measures/K279-1.tsv"]


def test_fetch_right_md5(tmp_path):
    path = fetch(URL, MD5, cache_dir=tmp_path)
    assert hashlib.md5(path.read_bytes()).hexdigest() == MD5
    assert fetch(URL, MD5, cache_dir=tmp_path) == path


def test_fetch_reuses_cached_file(tmp_path, monkeypatch):
    path = fetch(URL, MD5, cache_dir=tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded again"))
    assert fetch(URL, MD5, cache_dir=tmp_path) == path


def test_fetch_wrong_md5_leaves_nothing(tmp_path):
    with pytest.raises(ChecksumError) as exc:
        fetch(URL, "0" * 32, cache_dir=tmp_path)
    assert exc.value.expected == "0" * 32 and exc.value.actual == MD5 and exc.value.url == URL
    assert list(tmp_path.iterdir()) == []


def test_fetch_member(tmp_path):
    member = "2_Annotations/ann_score_localkey/Beethoven_Op049No2-01.csv"
    path = fetch_member(BPSD_ZIP, f"{BPSD_ROOT}/{member}", BPSD_MEMBERS[member], cache_dir=tmp_path)
    assert hashlib.md5(path.read_bytes()).hexdigest() == BPSD_MEMBERS[member]
    with pytest.raises(ChecksumError):
        fetch_member(BPSD_ZIP, f"{BPSD_ROOT}/{member}", "0" * 32, cache_dir=tmp_path / "other")
    assert not any((tmp_path / "other").iterdir())
