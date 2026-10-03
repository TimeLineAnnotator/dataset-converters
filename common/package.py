"""Build distributable zip packages of converted files."""
import zipfile
from pathlib import Path

_CC = "https://creativecommons.org/licenses/"
LICENCES = {
    "CC-BY-3.0": ("Creative Commons Attribution 3.0 Unported", _CC + "by/3.0/"),
    "CC-BY-4.0": ("Creative Commons Attribution 4.0 International", _CC + "by/4.0/"),
    "CC-BY-SA-4.0": ("Creative Commons Attribution-ShareAlike 4.0 International", _CC + "by-sa/4.0/"),
    "CC-BY-NC-SA-4.0": ("Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International", _CC + "by-nc-sa/4.0/"),
    "ODbL-1.0": ("Open Data Commons Open Database License v1.0", "https://opendatacommons.org/licenses/odbl/1-0/"),
    "MIT": ("MIT License", "https://opensource.org/license/mit"),
}

_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_package(name, files, licence, notes, *, out_dir) -> Path:
    """Write ``out_dir/<name>.zip`` holding ``files``, a LICENSE and a NOTICE.md under ``<name>/``.

    ``licence`` is an SPDX id from ``LICENCES``. The archive is reproducible: entries are
    sorted and carry fixed timestamps and permissions.
    """
    if licence not in LICENCES:
        raise ValueError(f"unknown licence {licence!r}; known: {', '.join(sorted(LICENCES))}")
    licence_name, licence_url = LICENCES[licence]
    entries = {f"{name}/{Path(f).name}": Path(f).read_bytes() for f in files}
    entries[f"{name}/LICENSE"] = f"{licence_name}\n{licence_url}\n".encode()
    entries[f"{name}/NOTICE.md"] = notes.encode()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.zip"
    with zipfile.ZipFile(path, "w") as z:
        for entry in sorted(entries):
            info = zipfile.ZipInfo(entry, _TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            z.writestr(info, entries[entry])
    return path
