"""Add Dezrann's sonata-form structure and texture to the converted DCML Mozart files.

    python dezrann-mozart/convert.py --dcml DIR --out DIR [--only ID ...] [--no-tilia]

``--dcml`` is the output directory of dcml-mozart/convert.py (it holds ``tla/<ID>.tla``). The merged files
go to ``OUT/tla`` and are built locally, never shipped: they hold DCML's CC BY-NC-SA timelines next to
Dezrann's ODbL ones. What ships is ``OUT/package``: Dezrann's layers alone, as CSVs by bar.

The time convention is DCML's: one second stands for one quarter note, so a Dezrann position of q quarter
notes is at q seconds. Labels are imported BY TIME, because a bar number that occurs twice (voltas) would
get a by-measure label twice.
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from common.download import fetch  # noqa: E402
from common.lint import lint  # noqa: E402
from common.package import build_package  # noqa: E402
from common.runner import run_script  # noqa: E402
from format_converters.dez import read_dez, to_tilia_rows  # noqa: E402

URL = "https://entrepot.recherche.data.gouv.fr/api/access/datafile/596605"
MD5 = "3466d49365ac30a59a6883dd522a5d62"
ROOT = "mozart-piano-sonatas/"
PACKAGE_NAME = "dezrann-mozart-tilia-layers"
LICENCE_ID = "ODbL-1.0"

PIECES = [f"K{n}-{m}" for n in (279, 280, 283) for m in (1, 2, 3)]
# Dezrann's label type -> (kind of TiLiA timeline's name, file stem)
LAYERS = {"Structure": ("Structure (Dezrann)", "structure"), "Texture": ("Texture (Dezrann)", "texture")}
LEFT_OUT = ("Harmony", "Cadence", "Local Key", "Phrase", "Positive Feedback", "Comment")
BAR_FIELDS = ["start", "start_fraction", "end", "end_fraction", "level", "label", "comments"]
TIME_FIELDS = ["start", "end", "level", "label", "comments"]


def fetch_archive(cache_dir=None) -> Path:
    """The Dezrann archive, downloaded into the cache and checked by md5."""
    return fetch(URL, MD5, cache_dir=cache_dir)


def extract(archive, pieces, dest) -> Path:
    """Unzip the texture analyses and measure maps of ``pieces`` under ``dest``; returns the dataset root."""
    dest = Path(dest)
    with zipfile.ZipFile(archive) as z:
        for piece in pieces:
            for member in (f"analysis/{piece}_texture.dez", f"measure-map/{piece}.mm.json"):
                target = dest / ROOT / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(ROOT + member))
    return dest / ROOT


def _fnum(q: Fraction) -> float:
    return float(q)


def layer_rows(piece: str, root) -> dict[str, dict]:
    """Per Dezrann layer: ``bars`` (rows by bar, as to_tilia_rows gives them) and ``times`` (rows in seconds).

    Levels are worked out per layer, so the two Structure levels (sections over subjects) do not mix with
    the Texture hierarchy. A label that runs past the last bar ends with the piece.
    """
    root = Path(root)
    labels = read_dez(root / "analysis" / f"{piece}_texture.dez")
    measure_map = json.loads((root / "measure-map" / f"{piece}.mm.json").read_text(encoding="utf-8"))
    last = max(Fraction(str(m["qstamp"])) + Fraction(str(m["actual_length"])) for m in measure_map)
    layers = {}
    for typ in LAYERS:
        own = [lab for lab in labels if lab.type == typ]
        bars = to_tilia_rows(own, measure_map, "hierarchy")
        times = [{"start": _fnum(lab.start), "end": _fnum(min(lab.end, last)), "level": row["level"],
                  "label": row["label"], "comments": row["comments"]} for lab, row in zip(own, bars)]
        layers[typ] = {"bars": bars, "times": times}
    return layers


def write_csv(path, fields, rows) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return Path(path)


def check_bar_numbers(piece: str, root, dcml_tla) -> dict:
    """Compare Dezrann's measure map with DCML's Measures timeline: bar numbers (pickups and voltas
    included) and bar start times, in quarter notes. Returns what was found."""
    measure_map = json.loads((Path(root) / "measure-map" / f"{piece}.mm.json").read_text(encoding="utf-8"))
    data = json.loads(Path(dcml_tla).read_text())
    tl = next(t for t in data["timelines"].values() if t.get("name") == "Measures")
    times = sorted(c["time"] for c in tl["components"].values())
    starts, i = [], 0
    for beats in tl["beats_in_measure"]:
        starts.append(times[i])
        i += beats
    mm_numbers = [m["number"] for m in measure_map]
    mm_starts = [m["qstamp"] for m in measure_map]
    return {
        "bars": len(measure_map),
        "numbers_agree": mm_numbers == tl["measure_numbers"],
        "starts_agree": len(starts) == len(mm_starts) and all(abs(a - b) < 1e-6 for a, b in zip(starts, mm_starts)),
        "pickup": measure_map[0]["number"] == 0 or measure_map[0]["actual_length"] < measure_map[0]["nominal_length"],
        "repeated_numbers": sorted({n for n in mm_numbers if mm_numbers.count(n) > 1}),
    }


def _q(value: str) -> str:
    return '"' + " ".join(str(value).replace('"', "'").split()) + '"'


def write_script(source_tla: Path, out_tla: Path, structure_csv: Path, texture_csv: Path) -> str:
    """The text of the TiLiA script for one movement. Only this function depends on how TiLiA is driven
    (today ``open`` is a command of the script; a non-interactive ``tilia run`` will need it too)."""
    return "\n".join([
        f"open {source_tla}",
        f"timelines add hierarchy --name {_q(LAYERS['Structure'][0])}",
        f"timelines add hierarchy --name {_q(LAYERS['Texture'][0])}",
        f"timelines import hierarchy by-time --target-name {_q(LAYERS['Structure'][0])} --file {structure_csv}",
        f"timelines import hierarchy by-time --target-name {_q(LAYERS['Texture'][0])} --file {texture_csv}",
        f"save {out_tla} --overwrite",
    ]) + "\n"


def _components(by_name, name):
    c = by_name[name].get("components", {})
    return list(c.values()) if isinstance(c, dict) else list(c)


def count_tla(path) -> dict[str, int]:
    """Components per timeline of a saved .tla file."""
    data = json.loads(Path(path).read_text())
    by_name = {t["name"]: t for t in data["timelines"].values() if t.get("name")}
    return {name: len(_components(by_name, name)) for name in by_name}


def _digest(path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def convert(pieces, dcml_dir, out, *, archive=None, run_tilia=True, jobs: int = 4) -> dict:
    """Build the CSVs by bar and by time, the scripts and (with ``run_tilia``) the merged files.

    Returns, per movement: the bar-number check, the components of the two new timelines and the labels
    counted in the .dez file. DCML's files are only read: TiLiA opens a copy.
    """
    out, dcml_dir = Path(out), Path(dcml_dir)
    root = extract(archive or fetch_archive(), pieces, out / "dez")
    for sub in ("csv-by-bar", "csv-by-time", "scripts", "work", "tla"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    summary, scripts = {}, {}
    for piece in pieces:
        source = dcml_dir / "tla" / f"{piece}.tla"
        if not source.exists():
            raise FileNotFoundError(f"{source}: run dcml-mozart/convert.py --out {dcml_dir} --only {piece}")
        layers = layer_rows(piece, root)
        files = {}
        for typ, (name, stem) in LAYERS.items():
            write_csv(out / "csv-by-bar" / f"{piece}-{stem}.csv", BAR_FIELDS, layers[typ]["bars"])
            files[typ] = write_csv(out / "csv-by-time" / f"{piece}-{stem}.csv", TIME_FIELDS, layers[typ]["times"])
        work = shutil.copyfile(source, out / "work" / f"{piece}.tla")
        scripts[piece] = out / "scripts" / f"{piece}.txt"
        scripts[piece].write_text(write_script(Path(work).resolve(), (out / "tla" / f"{piece}.tla").resolve(),
                                               files["Structure"].resolve(), files["Texture"].resolve()),
                                  encoding="utf-8")
        summary[piece] = {"bar_numbers": check_bar_numbers(piece, root, source),
                          "dez_labels": {t: len(layers[t]["bars"]) for t in LAYERS}}
    if not run_tilia:
        return summary

    def run(piece):
        run_script(scripts[piece], check=True)
        return piece, count_tla(out / "tla" / f"{piece}.tla")

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        counted = dict(pool.map(run, pieces))
    for piece in pieces:
        before = count_tla(dcml_dir / "tla" / f"{piece}.tla")
        after = counted[piece]
        summary[piece]["dcml_unchanged"] = all(after.get(n) == c for n, c in before.items())
        summary[piece]["components"] = {typ: after[name] for typ, (name, _) in LAYERS.items()}
        summary[piece]["lint"] = lint(out / "tla" / f"{piece}.tla")
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def package(out: Path, package_dir: Path, pieces=PIECES) -> Path:
    """Zip Dezrann's layers alone, as CSVs by bar, with the ODbL LICENSE and NOTICE.md."""
    files = [Path(out) / "csv-by-bar" / f"{p}-{stem}.csv" for p in pieces for _, stem in LAYERS.values()]
    return build_package(PACKAGE_NAME, files, LICENCE_ID, (HERE / "NOTICE.md").read_text(encoding="utf-8"),
                         out_dir=package_dir)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dcml", required=True, help="output directory of dcml-mozart/convert.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="+", choices=PIECES)
    ap.add_argument("--no-tilia", action="store_true")
    args = ap.parse_args(argv)
    pieces = args.only or PIECES
    summary = convert(pieces, args.dcml, args.out, run_tilia=not args.no_tilia)
    if len(pieces) == len(PIECES):
        print(package(Path(args.out), Path(args.out) / "package"))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
