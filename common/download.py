"""Download files with checksums, and single members of remote zip files."""
import hashlib
import http.client
import io
import json
import os
import random
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


TIMEOUT = 60  # seconds without data before a request is given up
ATTEMPTS = 6  # tries of one request
BACKOFF_LIMIT = 60  # seconds, the longest wait between tries
CHUNK = 4 << 20  # bytes per request of a resumable download
CONNECTIONS = 4  # at a time: Zenodo answers more with 429
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    """The wait the server asks for, in seconds; the header's date form counts as no answer."""
    try:
        return max(0.0, float(error.headers.get("Retry-After", "")))
    except ValueError:
        return None


def _retrying(request, attempts: int = ATTEMPTS):
    """Call ``request`` until it works, waiting longer each time. HTTP errors that won't change are final."""
    for attempt in range(attempts):
        try:
            return request()
        except urllib.error.HTTPError as e:
            if e.code not in _RETRYABLE_STATUS or attempt == attempts - 1:
                raise
            wait = _retry_after(e)
        except (OSError, http.client.HTTPException):
            if attempt == attempts - 1:
                raise
            wait = None
        if wait is None:
            wait = min(BACKOFF_LIMIT, 2**attempt) * (0.5 + random.random() / 2)
        time.sleep(wait)


def _read_range(url: str, start: int, end: int) -> bytes:
    """Bytes ``start`` to ``end``, inclusive."""
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 206:
            raise OSError(f"{url}: the server does not support range requests")
        data = r.read()
    if len(data) != end - start + 1:
        raise OSError(f"{url}: short read of bytes {start}-{end}")
    return data


def _size(url: str) -> int:
    def head():
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=TIMEOUT) as r:
            return int(r.headers["Content-Length"])

    return _retrying(head)


class ChecksumError(Exception):
    def __init__(self, expected: str, actual: str, url: str):
        self.expected, self.actual, self.url = expected, actual, url
        super().__init__(f"md5 mismatch for {url}: expected {expected}, got {actual}")


def default_cache_dir() -> Path:
    env = os.environ.get("DATASET_CONVERTERS_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "dataset-converters"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_path(cache_dir, key: str, md5: str, name: str) -> Path:
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{key}\n{md5}".encode()).hexdigest()[:16]
    return cache_dir / f"{digest}-{name}"


def _store(url: str, md5: str, target: Path, write) -> Path:
    """Write through ``write(file)`` to a temporary file, verify it, and rename it to ``target``."""
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".partial-")
    tmp = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as f:
            write(f)
        actual = _md5(tmp)
        if actual != md5:
            raise ChecksumError(md5, actual, url)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def fetch(url: str, md5: str, *, cache_dir=None) -> Path:
    """Return the cached file for ``url``, downloading it first if needed; its md5 must match."""
    name = Path(url.split("?")[0]).name
    target = _cache_path(cache_dir, url, md5, name)
    if target.exists() and _md5(target) == md5:
        return target

    def write(f):
        def download():
            f.seek(0)
            f.truncate()
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                while chunk := r.read(1 << 20):
                    f.write(chunk)

        _retrying(download)

    return _store(url, md5, target, write)


def fetch_resumable(url: str, md5: str, *, cache_dir=None, attempts: int = 10, connections: int = CONNECTIONS) -> Path:
    """Like ``fetch``, for large files: parallel range requests, each retried on its own, and an interrupted
    download continues from the chunks it has. It uses the path ``fetch`` would, so ``fetch`` finds the file."""
    name = Path(url.split("?")[0]).name
    target = _cache_path(cache_dir, url, md5, name)
    if target.exists() and _md5(target) == md5:
        return target
    part = target.with_name(target.name + ".part")
    done_file = target.with_name(target.name + ".done")
    size = _size(url)
    count = -(-size // CHUNK)
    done = set(json.loads(done_file.read_text())) if part.exists() and done_file.exists() else set()
    with open(part, "ab") as f:
        f.truncate(size)
    lock = threading.Lock()

    with open(part, "r+b") as f:

        def work(i):
            start, end = i * CHUNK, min((i + 1) * CHUNK, size) - 1
            data = _retrying(lambda: _read_range(url, start, end), attempts)
            with lock:
                f.seek(start)
                f.write(data)
                f.flush()  # before the chunk counts as done
                done.add(i)
                done_file.write_text(json.dumps(sorted(done)))

        with ThreadPoolExecutor(connections) as pool:
            list(pool.map(work, [i for i in range(count) if i not in done]))

    actual = _md5(part)
    if actual != md5:
        part.unlink()
        done_file.unlink(missing_ok=True)
        raise ChecksumError(md5, actual, url)
    os.replace(part, target)
    done_file.unlink(missing_ok=True)
    return target


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file over HTTP range requests."""

    def __init__(self, url):
        self.url = url
        self.size = _size(url)
        self.pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        else:
            self.pos = self.size + offset
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        data = _retrying(lambda: _read_range(self.url, self.pos, end))
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def fetch_member(zip_url: str, member: str, md5: str, *, cache_dir=None) -> Path:
    """Return one member of a remote zip as a cached file, reading only that member (HTTP range requests)."""
    key = f"{zip_url}#{member}"
    target = _cache_path(cache_dir, key, md5, Path(member).name)
    if target.exists() and _md5(target) == md5:
        return target

    def write(f):
        archive = zipfile.ZipFile(io.BufferedReader(HttpRangeFile(zip_url), buffer_size=1 << 16))
        with archive.open(member) as src:
            while chunk := src.read(1 << 20):
                f.write(chunk)

    return _store(f"{zip_url}#{member}", md5, target, write)
