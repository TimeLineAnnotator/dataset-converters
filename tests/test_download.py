import hashlib
import http.server
import io
import json
import threading
import urllib.error
import urllib.request
import zipfile

import pytest

import common.download
from common.download import ChecksumError, fetch, fetch_member, fetch_resumable
from conftest import BPSD_MEMBERS, BPSD_ROOT, BPSD_ZIP, DCML_BASE, DCML_FILES

URL = DCML_BASE + "measures/K279-1.tsv"
MD5 = DCML_FILES["measures/K279-1.tsv"]


@pytest.mark.network
def test_fetch_right_md5(tmp_path):
    path = fetch(URL, MD5, cache_dir=tmp_path)
    assert hashlib.md5(path.read_bytes()).hexdigest() == MD5
    assert fetch(URL, MD5, cache_dir=tmp_path) == path


@pytest.mark.network
def test_fetch_reuses_cached_file(tmp_path, monkeypatch):
    path = fetch(URL, MD5, cache_dir=tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded again"))
    assert fetch(URL, MD5, cache_dir=tmp_path) == path


@pytest.mark.network
def test_fetch_wrong_md5_leaves_nothing(tmp_path):
    with pytest.raises(ChecksumError) as exc:
        fetch(URL, "0" * 32, cache_dir=tmp_path)
    assert exc.value.expected == "0" * 32 and exc.value.actual == MD5 and exc.value.url == URL
    assert list(tmp_path.iterdir()) == []


@pytest.mark.network
def test_fetch_member(tmp_path):
    member = "2_Annotations/ann_score_localkey/Beethoven_Op049No2-01.csv"
    path = fetch_member(BPSD_ZIP, f"{BPSD_ROOT}/{member}", BPSD_MEMBERS[member], cache_dir=tmp_path)
    assert hashlib.md5(path.read_bytes()).hexdigest() == BPSD_MEMBERS[member]
    with pytest.raises(ChecksumError):
        fetch_member(BPSD_ZIP, f"{BPSD_ROOT}/{member}", "0" * 32, cache_dir=tmp_path / "other")
    assert not any((tmp_path / "other").iterdir())


# ---------------------------------------------------------------- against a local server
class Server:
    """Serves ``body`` with range requests; ``failures`` are statuses (or (status, Retry-After)) to answer first."""

    def __init__(self, body):
        self.body, self.failures, self.requests = body, [], []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(outer.body)))
                self.end_headers()

            def do_GET(self):
                outer.requests.append(self.headers.get("Range"))
                if outer.failures:
                    failure = outer.failures.pop(0)
                    status, after = failure if isinstance(failure, tuple) else (failure, None)
                    self.send_response(status)
                    if after is not None:
                        self.send_header("Retry-After", after)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                data, status = outer.body, 200
                if self.headers.get("Range"):
                    start, end = self.headers["Range"].removeprefix("bytes=").split("-")
                    data, status = outer.body[int(start) : int(end) + 1], 206
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/file.bin"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def waits(monkeypatch):
    waited = []
    monkeypatch.setattr(common.download.time, "sleep", waited.append)
    return waited


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    made = []

    def make(body):
        made.append(Server(body))
        return made[-1]

    yield make
    for s in made:
        s.httpd.shutdown()
        s.httpd.server_close()


def md5(data):
    return hashlib.md5(data).hexdigest()


def test_fetch_waits_out_a_429_and_a_503(server, waits, tmp_path):
    s = server(b"x" * 100)
    s.failures = [429, 503]
    assert fetch(s.url, md5(s.body), cache_dir=tmp_path).read_bytes() == s.body
    assert len(s.requests) == 3
    assert len(waits) == 2 and waits[0] < waits[1] * 2 and all(w > 0 for w in waits)


def test_fetch_waits_as_long_as_the_server_asks(server, waits, tmp_path):
    s = server(b"x" * 100)
    s.failures = [(429, "7"), (429, "Wed, 21 Oct 2026 07:28:00 GMT")]
    fetch(s.url, md5(s.body), cache_dir=tmp_path)
    assert waits[0] == 7 and 0 < waits[1] <= 2


def test_fetch_gives_up_at_once_on_a_404(server, waits, tmp_path):
    s = server(b"x")
    s.failures = [404]
    with pytest.raises(urllib.error.HTTPError):
        fetch(s.url, md5(s.body), cache_dir=tmp_path)
    assert len(s.requests) == 1 and waits == [] and list(tmp_path.iterdir()) == []


def test_fetch_gives_up_after_its_attempts(server, waits, tmp_path):
    s = server(b"x")
    s.failures = [503] * 50
    with pytest.raises(urllib.error.HTTPError):
        fetch(s.url, md5(s.body), cache_dir=tmp_path)
    assert len(s.requests) == common.download.ATTEMPTS and list(tmp_path.iterdir()) == []


def test_fetch_member_retries_a_range(server, waits, tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("a/b.txt", "contents")
    s = server(buffer.getvalue())
    s.failures = [503]
    path = fetch_member(s.url, "a/b.txt", md5(b"contents"), cache_dir=tmp_path)
    assert path.read_bytes() == b"contents" and len(waits) == 1


@pytest.fixture
def small_chunks(monkeypatch):
    monkeypatch.setattr(common.download, "CHUNK", 10)


BODY = bytes(range(256)) * 2  # 52 chunks of 10 bytes, the last one short


def test_fetch_resumable(server, waits, small_chunks, tmp_path):
    s = server(BODY)
    s.failures = [429, 503]
    path = fetch_resumable(s.url, md5(BODY), cache_dir=tmp_path)
    assert path.read_bytes() == BODY
    assert [p.name for p in tmp_path.iterdir()] == [path.name]
    assert fetch(s.url, md5(BODY), cache_dir=tmp_path) == path  # where fetch looks
    assert len(s.requests) == 52 + 2


def test_fetch_resumable_continues_from_the_chunks_it_has(server, waits, small_chunks, tmp_path):
    s = server(BODY)
    s.failures = [404]  # final: the first run stops at once
    with pytest.raises(urllib.error.HTTPError):
        fetch_resumable(s.url, md5(BODY), cache_dir=tmp_path, connections=1)
    part = next(tmp_path.glob("*.part"))
    assert part.stat().st_size == len(BODY)

    # as if an earlier run had got chunks 0 to 4 and died
    part.write_bytes(BODY[:50] + bytes(len(BODY) - 50))
    part.with_suffix(".done").write_text(json.dumps(list(range(5))))
    s.requests.clear()
    path = fetch_resumable(s.url, md5(BODY), cache_dir=tmp_path)
    assert path.read_bytes() == BODY and len(s.requests) == 52 - 5
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_fetch_resumable_refuses_a_wrong_file_and_keeps_nothing(server, waits, small_chunks, tmp_path):
    s = server(BODY)
    with pytest.raises(ChecksumError):
        fetch_resumable(s.url, "0" * 32, cache_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_server_without_range_requests_is_an_error(server, waits, small_chunks, tmp_path, monkeypatch):
    s = server(BODY)
    real = common.download.urllib.request.Request
    # the server sees no Range header and answers with the whole file
    monkeypatch.setattr(common.download.urllib.request, "Request", lambda url, headers=None, method=None: real(url, method=method))
    with pytest.raises(OSError, match="range requests"):
        fetch_resumable(s.url, md5(BODY), cache_dir=tmp_path, attempts=1)
