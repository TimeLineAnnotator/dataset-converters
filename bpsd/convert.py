"""Convert the Beethoven Piano Sonata Dataset v2 (BPSD) to TiLiA files.

One .tla per movement and performance: 32 pieces x 11 performers. Run from the repository root:

    python bpsd/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia] [--zip ZIP [--audio]]

The BPSD files are read through ``common.download`` (pinned URL, md5 checksums). Per item the converter
writes ``DIR/csv/<ID>/*.csv`` and ``DIR/scripts/<ID>.txt``, runs the script with TiLiA and saves
``DIR/tla/<ID>.tla``; ``DIR/summary.json`` counts every layer in the saved file against the source rows.
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from common.download import default_cache_dir, fetch, fetch_member  # noqa: E402
from common.package import build_package  # noqa: E402
from common.runner import run_script  # noqa: E402

ZIP_URL = "https://zenodo.org/records/12783403/files/Beethoven_Piano_Sonata_Dataset_v2.zip?download=1"
ZIP_MD5 = "17f73a2d608fd6e6da65d3bd9dda1923"
ROOT = "Beethoven_Piano_Sonata_Dataset_v2/"
ANN = "2_Annotations/"
CHECKSUMS = Path(__file__).with_name("checksums.json")
PACKAGE_NAME = "bpsd-v2-tilia"
LICENCE = "CC-BY-3.0"
CORPUS = "Beethoven Piano Sonata Dataset (BPSD) v2, doi:10.5281/zenodo.12783403"
CITATION = (
    "Zeitler, J., Weiß, C., Arifi-Müller, V. and Müller, M. (2024) BPSD: A Coherent Multi-Version Dataset for "
    "Analyzing the First Movements of Beethoven's Piano Sonatas. Transactions of the International Society for "
    "Music Information Retrieval, 7(1), 195-212. https://doi.org/10.5334/tismir.196"
)

PIECES = [
    "Op002No1-01", "Op002No2-01", "Op002No3-01", "Op007-01", "Op010No1-01", "Op010No2-01", "Op010No3-01",
    "Op013-01", "Op014No1-01", "Op014No2-01", "Op022-01", "Op026-01", "Op027No1-01", "Op027No2-01",
    "Op028-01", "Op031No1-01", "Op031No2-01", "Op031No3-01", "Op049No1-01", "Op049No2-01", "Op053-01",
    "Op054-01", "Op057-01", "Op078-01", "Op079-01", "Op081a-01", "Op090-01", "Op101-01", "Op106-01",
    "Op109-01", "Op110-01", "Op111-01",
]
PERFORMERS = ["AB96", "AS35", "DB84", "FG58", "FG67", "FJ62", "JJ90", "MB97", "MC22", "VA81", "WK64"]
# the four recordings that BPSD's description calls "in the public domain and freely accessible for research
# purposes" (WK64 may still be protected in the EU until about 2035); the notebook's full run loads them from
# the archive, and no package ships them
AUDIO_PERFORMERS = ["AS35", "FG58", "FJ62", "WK64"]
ITEMS = [f"{piece}_{performer}" for piece in PIECES for performer in PERFORMERS]

TIMELINES = ("Measures", "Structure", "Harmony", "Chords (unparsed)")
NO_CHORD = {"N", "X", ""}
MOVEMENTS = {"01": "i", "02": "ii", "03": "iii"}
EPS = 1e-6


# ---------------------------------------------------------------- reading the archive
class RemoteSource:
    """Members of the remote archive, one at a time (HTTP range requests, checked against checksums.json)."""

    def __init__(self, checksums: dict[str, str] | None = None, cache_dir=None):
        self.checksums = checksums if checksums is not None else json.loads(CHECKSUMS.read_text())
        self.cache_dir = cache_dir

    def path(self, member: str) -> Path:
        try:
            md5 = self.checksums[member]
        except KeyError:
            raise KeyError(f"{member} has no checksum in {CHECKSUMS.name}") from None
        return fetch_member(ZIP_URL, ROOT + member, md5, cache_dir=self.cache_dir)


class DirSource:
    """Members of an unpacked archive (the folder that holds ``0_RawData``, ``1_Audio``, ...)."""

    def __init__(self, root):
        self.root = Path(root)

    def path(self, member: str) -> Path:
        return self.root / member


class ZipSource:
    """Members of the downloaded archive (its md5 was checked by ``fetch``), extracted into the cache."""

    def __init__(self, zip_path, cache_dir=None):
        self.zip_path = Path(zip_path)
        self.target = Path(cache_dir or default_cache_dir()) / f"bpsd-v2-{ZIP_MD5[:8]}"

    def path(self, member: str) -> Path:
        target = self.target / member
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".partial")
            with zipfile.ZipFile(self.zip_path) as z, z.open(ROOT + member) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            tmp.replace(target)
        return target


def download_archive(cache_dir=None) -> Path:
    """The whole archive, in the cache; ``fetch`` checks its md5."""
    return fetch(ZIP_URL, ZIP_MD5, cache_dir=cache_dir)


def read_table(path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return [{(k or "").strip(): (v or "").strip().strip('"') for k, v in row.items()}
                for row in csv.DictReader(f, delimiter=";")]


def annotation(source, kind: str, item: str) -> list[dict[str, str]]:
    piece, performer = split_id(item)
    return read_table(source.path(f"{ANN}ann_audio_{kind}/Beethoven_{piece}_{performer}.csv"))


def split_id(item: str) -> tuple[str, str]:
    piece, _, performer = item.rpartition("_")
    return piece, performer


def performer_names(source) -> dict[str, dict[str, str]]:
    rows = read_table(source.path("0_RawData/audio_ripped/audio_versions_metadata.csv"))
    return {r["ID"]: r for r in rows}


# ---------------------------------------------------------------- printed bar numbers
@functools.lru_cache(maxsize=None)
def _bar_numbers(repetitions: str, unfolded: str, pickup: bool):
    from bpsd.bars import printed_numbers
    numbers, distances = printed_numbers(repetitions, unfolded, pickup)
    return tuple(numbers), tuple(distances)


def has_pickup(source, piece: str) -> bool:
    """Whether the movement opens with a pickup: BPSD's ann_audio_measure starts below bar 1 (000.750).

    All performances of a movement must agree.
    """
    found = {}
    for performer in PERFORMERS:
        first = float(annotation(source, "measure", f"{piece}_{performer}")[0]["measure"])
        found[performer] = first < 1
    if len(set(found.values())) != 1:
        raise ValueError(f"{piece}: the performances disagree on a pickup: "
                         + ", ".join(p for p, v in found.items() if v) + " start below bar 1, "
                         + ", ".join(p for p, v in found.items() if not v) + " do not")
    return next(iter(found.values()))


def bar_numbers(source, piece: str) -> tuple[tuple[int, ...], bool]:
    """The printed number of every bar of the piece's unfolded score, and whether it opens with a pickup."""
    repetitions = source.path(f"0_RawData/score_xml_repetitions/Beethoven_{piece}.xml")
    unfolded = source.path(f"0_RawData/score_xml_unfolded/Beethoven_{piece}.xml")
    pickup = has_pickup(source, piece)
    numbers, _ = _bar_numbers(str(repetitions), str(unfolded), pickup)
    return numbers, pickup


def measure_rows(rows: list[dict[str, str]], numbers: tuple[int, ...], pickup: bool) -> list[dict]:
    """One beat per row of ann_audio_measure, each opening a bar, with the printed number to show.

    A row's ``measure`` is the unfolded bar (fractional for a partial bar). The last row is the end:
    it shows the number after the last bar.
    """
    out = []
    first = 0 if pickup else 1  # the unfolded bar number of numbers[0]
    end = float(rows[-1]["time"])
    for i, row in enumerate(rows):
        time, bar = float(row["time"]), float(row["measure"])
        if i == len(rows) - 2 and time >= end:
            # BPSD data problem (WK64, Op. 26 and Op. 31 No. 2): the last bar starts after the end row.
            # The bar is kept, one millisecond before the end, so that the grid stays ascending.
            row = {**row, "time": f"{end - 0.001:.3f}"}
            time = float(row["time"])
        if i < len(rows) - 1:
            index = int(bar) - first
            if not 0 <= index < len(numbers):
                raise ValueError(f"bar {bar} is not in the unfolded score ({len(numbers)} bars)")
            number = numbers[index]
        else:
            last = int(-(-bar // 1)) - 1  # the last bar that has music in it
            index = min(max(last, first) - first, len(numbers) - 1)
            number = numbers[index] + 1
        if out and time < float(out[-1]["time"]):
            raise ValueError("bar starts are not in ascending order")
        out.append({"time": row["time"], "measure": number, "is_first_in_measure": "true"})
    return out


# ---------------------------------------------------------------- structure, keys, chords
def structure_rows(fine: list[dict[str, str]], coarse: list[dict[str, str]]) -> list[dict]:
    """Level 2 = the coarse sections, level 1 = the fine ones (the part of the label after ':').

    BPSD repeats some rows verbatim; TiLiA keeps one.
    """
    out = []
    for level, rows in ((2, coarse), (1, fine)):
        seen = set()
        for r in rows:
            key = (r["start"], r["end"], r["structure"])
            if key in seen:
                continue
            seen.add(key)
            label = r["structure"].split(":", 1)[-1].strip() if level == 1 else r["structure"]
            out.append({"start": r["start"], "end": r["end"], "level": level, "label": label, "comments": ""})
    out.sort(key=lambda r: (float(r["start"]), -r["level"], float(r["end"])))
    return out


@functools.lru_cache(maxsize=None)
def _key(label: str) -> str:
    from format_converters.harmony import translate_key
    return translate_key(label, "bps-fh")


@functools.lru_cache(maxsize=None)
def _chord(roman: str, key: str, extended: str):
    from format_converters import _harte
    from format_converters.harmony import translate_chord
    return translate_chord(roman, "bps-fh", key, _harte.pitch_classes(extended))


def harmony_rows(localkeys: list[dict[str, str]], chords: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """The rows of the "Harmony" timeline (keys before the chords at the same time) and of "Chords (unparsed)"."""
    keys = [(float(r["start"]), 0, {
        "harmony_or_key": "key", "time": r["start"], "symbol": _key(r["localkey"]), "display_mode": "letter",
        "custom_text": "", "comments": ""}) for r in localkeys]
    rows, unparsed = [], []
    for r in chords:
        if r["shorthand"] in NO_CHORD:
            continue
        result = _chord(r["roman"], _key(r["localkey"]), r["extended"])
        if result.outcome == "none":
            unparsed.append({"time": r["start"], "label": r["roman"], "comments": result.comments})
        elif result.outcome == "no_chord":
            continue
        else:
            rows.append((float(r["start"]), 1, {
                "harmony_or_key": "harmony", "time": r["start"], "symbol": result.symbol,
                "display_mode": result.display_mode, "custom_text": result.custom_text,
                "comments": result.comments}))
    merged = sorted(keys + rows, key=lambda t: (t[0], t[1]))
    return [r for _, _, r in merged], unparsed


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path


# ---------------------------------------------------------------- metadata and script
def piece_title(piece: str) -> str:
    m = re.fullmatch(r"Op(\d+)([a-z]?)(?:No(\d+))?-(\d\d)", piece)
    opus, suffix, number, movement = m.groups()
    parts = [f"Op. {int(opus)}{suffix}"] + ([f"No. {int(number)}"] if number else [])
    return "Piano Sonata " + " ".join(parts) + ", " + MOVEMENTS[movement]


def metadata_for(item: str, performer_name: str) -> dict[str, str]:
    piece, performer = split_id(item)
    return {
        "title": piece_title(piece),
        "composer": "Ludwig van Beethoven",
        "performer": performer_name,
        "corpus": CORPUS,
        "licence": "CC BY 3.0",
        "notes": (
            f"Annotations by the BPSD authors: Johannes Zeitler, Christof Weiß, Vlora Arifi-Müller and Meinard Müller "
            f"(doi:10.5281/zenodo.12783403, CC BY 3.0). {CITATION}. Converted to TiLiA files; "
            f"the annotations refer to BPSD's modified audio (see NOTICE.md)."
        ),
    }


def write_script(item: str, csvs: dict[str, Path], tla: Path, metadata: dict[str, str], *,
                 media: Path | None = None, media_length: float | None = None) -> str:
    """The TiLiA command script of one item. The only place that knows the command syntax."""
    lines = [f'metadata set "{k}" "{v}"' for k, v in metadata.items()]
    if media is not None:
        lines.append(f"load-media {media}")
    else:
        lines.append(f"metadata set-media-length {media_length}")
    lines += [
        'timelines add beat --name "Measures" --beat-pattern 1',
        'timelines add hierarchy --name "Structure"',
        'timelines add harmony --name "Harmony"',
        'timelines add marker --name "Chords (unparsed)"',
        f'timelines import beat --target-name "Measures" --file {csvs["measures"]}',
        f'timelines import hierarchy by-time --target-name "Structure" --file {csvs["structure"]}',
        f'timelines import harmony by-time --target-name "Harmony" --file {csvs["harmony"]}',
        f'timelines import marker by-time --target-name "Chords (unparsed)" --file {csvs["unparsed"]}',
        f"save {tla} --overwrite",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- one item
def prepare_item(item: str, source, out: Path, *, audio_source=None, names=None) -> dict:
    """Write the CSVs and the script of one item; return what the later steps need."""
    piece, performer = split_id(item)
    names = names or performer_names(source)
    measures = annotation(source, "measure", item)
    numbers, pickup = bar_numbers(source, piece)
    localkeys = annotation(source, "localkey", item)
    chords = annotation(source, "chord", item)
    harmony, unparsed = harmony_rows(localkeys, chords)
    structure = structure_rows(annotation(source, "structureFine", item), annotation(source, "structureCoarse", item))
    beat_rows = measure_rows(measures, numbers, pickup)

    folder = out / "csv" / item
    csvs = {
        "measures": write_csv(folder / "measures.csv", ["time", "measure", "is_first_in_measure"], beat_rows),
        "structure": write_csv(folder / "structure.csv", ["start", "end", "level", "label", "comments"], structure),
        "harmony": write_csv(folder / "harmony.csv", ["harmony_or_key", "time", "symbol", "display_mode", "custom_text", "comments"], harmony),
        "unparsed": write_csv(folder / "unparsed.csv", ["time", "label", "comments"], unparsed),
    }
    tla = out / "tla" / f"{item}.tla"
    media = audio_source.path(f"1_Audio/Beethoven_{item}.wav") if audio_source and performer in AUDIO_PERFORMERS else None
    script = write_script(item, {k: v.resolve() for k, v in csvs.items()}, tla.resolve(),
                          metadata_for(item, names[performer]["Performer"]),
                          media=media, media_length=float(measures[-1]["time"]))
    script_path = out / "scripts" / f"{item}.txt"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    tla.parent.mkdir(parents=True, exist_ok=True)
    return {
        "script": script_path, "tla": tla,
        "source_rows": {
            "Measures": len(measures),
            "Structure": sum(1 for r in structure),
            "Harmony/keys": len(localkeys),
            "Harmony/chords": sum(1 for r in chords if r["shorthand"] not in NO_CHORD),
        },
    }


def count_tla(path: Path) -> dict[str, int]:
    data = json.loads(Path(path).read_text())
    timelines = {t["name"]: t for t in data["timelines"].values() if t.get("name")}
    comps = lambda t: list(t.get("components", {}).values())
    harmony = comps(timelines["Harmony"])
    return {
        "Measures": len(timelines["Measures"].get("beats_in_measure") or []),
        "Structure": len(comps(timelines["Structure"])),
        "Harmony/keys": sum(1 for c in harmony if "quality" not in c),
        "Harmony/chords": sum(1 for c in harmony if "quality" in c) + len(comps(timelines["Chords (unparsed)"])),
    }


def convert(items: list[str], out, *, source=None, audio_source=None, run_tilia: bool = True, tilia=None) -> dict:
    out = Path(out)
    source = source or RemoteSource()
    names = performer_names(source)
    summary = {}
    for item in items:
        prepared = prepare_item(item, source, out, audio_source=audio_source, names=names)
        if run_tilia:
            run_script(prepared["script"], tilia=tilia, check=True)
            found = count_tla(prepared["tla"])
            summary[item] = {layer: {"components": found[layer], "source_rows": n}
                             for layer, n in prepared["source_rows"].items()}
        else:
            summary[item] = {layer: {"components": None, "source_rows": n}
                             for layer, n in prepared["source_rows"].items()}
    if run_tilia:
        (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


# ---------------------------------------------------------------- the package
def notice_text() -> str:
    return (Path(__file__).with_name("NOTICE.md")).read_text(encoding="utf-8")


def package(out, package_dir) -> Path:
    """Zip the .tla files of ``out/tla`` without media or file paths, with LICENSE and NOTICE.md."""
    out, package_dir = Path(out), Path(package_dir)
    clean = package_dir / "_clean"
    shutil.rmtree(clean, ignore_errors=True)
    clean.mkdir(parents=True)
    files = []
    for tla in sorted((out / "tla").glob("*.tla")):
        data = json.loads(tla.read_text())
        data["file_path"] = ""
        data["media_path"] = ""
        target = clean / tla.name
        target.write_text(json.dumps(data), encoding="utf-8")
        files.append(target)
    try:
        return build_package(PACKAGE_NAME, files, LICENCE, notice_text(), out_dir=package_dir)
    finally:
        shutil.rmtree(clean, ignore_errors=True)


# ---------------------------------------------------------------- checksums of the members we read
def checksum_members() -> list[str]:
    members = ["0_RawData/audio_ripped/audio_versions_metadata.csv"]
    for piece in PIECES:
        members += [f"0_RawData/score_xml_{k}/Beethoven_{piece}.xml" for k in ("repetitions", "unfolded")]
    for item in ITEMS:
        piece, performer = split_id(item)
        members += [f"{ANN}ann_audio_{k}/Beethoven_{piece}_{performer}.csv"
                    for k in ("measure", "structureFine", "structureCoarse", "localkey", "chord")]
    return members


def write_checksums(zip_path) -> None:
    import hashlib
    sums = {}
    with zipfile.ZipFile(zip_path) as z:
        for member in checksum_members():
            sums[member] = hashlib.md5(z.read(ROOT + member)).hexdigest()
    CHECKSUMS.write_text(json.dumps(sums, indent=0, sort_keys=True) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="output directory")
    ap.add_argument("--only", nargs="+", metavar="ID", help="convert only these items, e.g. Op002No1-01_AB96")
    ap.add_argument("--package", metavar="DIR", help="build the package zip in DIR")
    ap.add_argument("--no-tilia", action="store_true", help="write the CSVs and scripts, but do not run TiLiA")
    ap.add_argument("--zip", help="the downloaded archive: read from it instead of the remote one")
    ap.add_argument("--audio", action="store_true", help="load the four recordings of the archive (AS35, FG58, FJ62, WK64; needs --zip)")
    ap.add_argument("--write-checksums", metavar="ZIP", help="regenerate checksums.json from a downloaded archive")
    args = ap.parse_args(argv)
    if args.write_checksums:
        write_checksums(args.write_checksums)
        return 0
    if not args.out:
        ap.error("--out is required")
    if args.audio and not args.zip:
        ap.error("--audio needs --zip")
    items = args.only or ITEMS
    unknown = [i for i in items if i not in ITEMS]
    if unknown:
        ap.error(f"unknown item(s): {' '.join(unknown)}")
    source = ZipSource(args.zip) if args.zip else RemoteSource()
    convert(items, args.out, source=source, audio_source=source if args.audio else None, run_tilia=not args.no_tilia)
    if args.package:
        if args.no_tilia:
            ap.error("--package needs the .tla files: leave out --no-tilia")
        print(package(args.out, args.package))
    return 0


if __name__ == "__main__":
    sys.exit(main())
