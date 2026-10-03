"""Download files with checksums, and single members of remote zip files."""
import hashlib
import io
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path


TIMEOUT = 60  # seconds without data before a request is given up


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
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            while chunk := r.read(1 << 20):
                f.write(chunk)

    return _store(url, md5, target, write)


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file over HTTP range requests."""

    def __init__(self, url):
        self.url = url
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            self.size = int(r.headers["Content-Length"])
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
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    data = r.read()
                break
            except OSError:
                if attempt == 2:
                    raise
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
