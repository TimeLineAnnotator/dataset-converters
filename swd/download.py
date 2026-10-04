"""Resumable, parallel download of the whole SWD archive.

Zenodo serves a single long transfer slowly and often stalls it, and ``common.download.fetch`` then starts
again from zero. This downloads the archive in chunks, several at a time, each by an HTTP range request that
is retried on its own, and it continues an interrupted download from the chunks it already has. It writes to
the path ``fetch`` would use, so ``fetch`` finds the finished file in the cache. It belongs in ``common/``
once that is open for changes.
"""
import http.client
import json
import os
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common.download import ChecksumError, _cache_path, _md5, fetch

TIMEOUT = 60  # seconds without data
CHUNK = 4 << 20
CONNECTIONS = 16


def _size(url):
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=TIMEOUT) as r:
        return int(r.headers["Content-Length"])


def _read_chunk(url, start, end):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 206:
            raise OSError("the server does not support range requests")
        data = r.read()
    if len(data) != end - start + 1:
        raise OSError("short chunk")
    return data


def fetch_resumable(url: str, md5: str, *, cache_dir=None, attempts: int = 50, connections: int = CONNECTIONS):
    """Like ``common.download.fetch``, but in parallel chunks, and an interrupted download is continued."""
    name = url.split("?")[0].rsplit("/", 1)[-1]
    target = _cache_path(cache_dir, url, md5, name)
    if target.exists() and _md5(target) == md5:
        return target
    part = target.with_name(target.name + ".part")
    done_file = target.with_name(target.name + ".done")
    size = _size(url)
    count = -(-size // CHUNK)
    done = set(json.loads(done_file.read_text())) if done_file.exists() and part.exists() else set()
    if part.exists() and not done_file.exists():  # a sequential download of an earlier version
        done = set(range(part.stat().st_size // CHUNK))
    if not part.exists():
        done = set()
    with open(part, "ab"):
        pass
    os.truncate(part, size)
    lock = threading.Lock()
    fd = os.open(part, os.O_WRONLY)

    def work(i):
        start, end = i * CHUNK, min((i + 1) * CHUNK, size) - 1
        for attempt in range(attempts):
            try:
                data = _read_chunk(url, start, end)
                break
            except (OSError, http.client.HTTPException):
                if attempt == attempts - 1:
                    raise
        os.pwrite(fd, data, start)
        with lock:
            done.add(i)
            done_file.write_text(json.dumps(sorted(done)))

    try:
        with ThreadPoolExecutor(connections) as pool:
            list(pool.map(work, [i for i in range(count) if i not in done]))
    finally:
        os.close(fd)
    actual = _md5(part)
    if actual != md5:
        part.unlink()
        done_file.unlink(missing_ok=True)
        raise ChecksumError(md5, actual, url)
    os.replace(part, target)
    done_file.unlink(missing_ok=True)
    return fetch(url, md5, cache_dir=cache_dir)
