"""Convert DCML's Annotated Mozart Piano Sonatas (v2.3) into TiLiA files, one per movement.

    python dcml-mozart/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia]

There is no recording: one second stands for one quarter note (the quarter-second convention).
Every label sits BY TIME at its row's quarterbeats_all_endings, so no bar fractions are needed.
"""
import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
import shutil
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from common.download import fetch  # noqa: E402
from common.lint import lint  # noqa: E402
from common.package import build_package  # noqa: E402
from common.runner import run_script  # noqa: E402

COMMIT = "5337257a5318711e6302cfe85c3f1a6ade3c6271"
BASE_URL = f"https://raw.githubusercontent.com/DCMLab/mozart_piano_sonatas/{COMMIT}/"
PACKAGE_NAME = "dcml-mozart-v2.3-tilia"
LICENCE_ID = "CC-BY-NC-SA-4.0"
LICENCE = "CC BY-NC-SA 4.0"
CORPUS = "The Annotated Mozart Sonatas (DCMLab/mozart_piano_sonatas), v2.3, DOI 10.5281/zenodo.7424962"
TIME_UNIT = "quarter notes (no recording: one second stands for one quarter note)"
CITATION = (
    "Hentschel, J., Neuwirth, M. and Rohrmeier, M. (2021) The Annotated Mozart Sonatas: Score, harmony, "
    "and cadence. Transactions of the International Society for Music Information Retrieval, 4(1), 67-80. "
    "https://doi.org/10.5334/tismir.63"
)

MD5S = json.loads((HERE / "md5s.json").read_text())
PIECES = [line.strip().removesuffix(".harmonies.tsv") for line in (HERE / "dcml_files.txt").read_text().split()]

LAYERS = ("Measures", "Harmony/keys", "Harmony/chords", "Cadences", "Phrases")

BEAT_FIELDS = ["time", "measure", "is_first_in_measure"]
HARMONY_FIELDS = ["harmony_or_key", "time", "symbol", "display_mode", "custom_text", "comments"]
MARKER_FIELDS = ["time", "label", "comments"]
PHRASE_FIELDS = ["start", "end", "level", "label", "comments"]


# --------------------------------------------------------------------------- reading the source
def fetch_sources(pieces=PIECES, cache_dir=None) -> dict[str, Path]:
    """Download (checksummed, cached) the files of ``pieces`` and metadata.tsv; relative path -> local path."""
    rels = ["metadata.tsv"]
    for p in pieces:
        rels += [f"harmonies/{p}.harmonies.tsv", f"measures/{p}.measures.tsv"]
    return {rel: fetch(BASE_URL + rel, MD5S[rel], cache_dir=cache_dir) for rel in rels}


def read_tsv(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f, delimiter="\t")]


def read_metadata(path) -> dict[str, dict]:
    return {r["piece"]: r for r in read_tsv(path)}


def bar_start_column(measures: list[dict]) -> str:
    return "quarterbeats_all_endings" if "quarterbeats_all_endings" in measures[0] else "quarterbeats"


def label_time(row: dict) -> Fraction:
    """A harmony row's time in quarter notes; the all-endings column is filled on every row."""
    return Fraction(row["quarterbeats_all_endings"] or row["quarterbeats"])


def seconds(q: Fraction) -> str:
    return repr(float(q))


# --------------------------------------------------------------------------- the layers
@dataclass
class Bar:
    mn: int
    start: Fraction
    nominal: Fraction  # length of the time signature's bar, in quarter notes
    actual: Fraction  # act_dur in quarter notes
    numerator: int

    @property
    def n_beats(self) -> int:
        return max(1, round(self.numerator * self.actual / self.nominal))

    @property
    def end(self) -> Fraction:
        return self.start + self.actual


def read_bars(measures: list[dict]) -> list[Bar]:
    col = bar_start_column(measures)
    bars = []
    for r in measures:
        num, den = map(int, r["timesig"].split("/"))
        bars.append(Bar(int(r["mn"]), Fraction(r[col]), Fraction(4 * num, den), 4 * Fraction(r["act_dur"]), num))
    return bars


def beat_rows(bars: list[Bar]) -> list[dict]:
    """numerator beats per bar over its nominal length; a partial bar keeps the first round(...) of them."""
    rows = []
    for bar in bars:
        step = bar.nominal / bar.numerator
        for i in range(bar.n_beats):
            rows.append({"time": seconds(bar.start + i * step), "measure": bar.mn,
                         "is_first_in_measure": "true" if i == 0 else "false"})
    return rows


def dcml_truth(row: dict) -> tuple | None:
    """The chord's (pitch classes, bass pitch class) from fifths above the local tonic."""
    from format_converters.harmony import _dcml_local_fifths

    if not row["chord_tones"]:
        return None
    fifths, _ = _dcml_local_fifths(row["globalkey"], row["localkey"])
    tones = [int(x) for x in row["chord_tones"].split(",")]
    if row["added_tones"]:
        tones += [int(x) for x in row["added_tones"].split(",")]
    return frozenset((7 * (fifths + t)) % 12 for t in tones), (7 * (fifths + int(row["bass_note"]))) % 12


def harmony_layers(harmonies: list[dict]) -> tuple[list[dict], list[dict]]:
    """(rows of the harmony CSV, rows of the unparsed-chords CSV). Keys come before chords at the same time."""
    from format_converters.harmony import translate_chord, translate_key

    harmony, unparsed = [], []
    previous = None
    for r in harmonies:
        t = seconds(label_time(r))
        key = translate_key(r["localkey"], "dcml", globalkey=r["globalkey"])
        if r["localkey"] != previous:
            previous = r["localkey"]
            harmony.append({"harmony_or_key": "key", "time": t, "symbol": key, "display_mode": "letter",
                            "custom_text": "", "comments": ""})
        if r["chord"] in ("", "@none"):
            continue
        truth = dcml_truth(r)
        if truth is None:
            unparsed.append({"time": t, "label": r["chord"], "comments": "the source row has no chord tones"})
            continue
        res = translate_chord(r["chord"], "dcml", key, truth)
        if res.outcome == "none":
            unparsed.append({"time": t, "label": r["chord"], "comments": res.comments})
        elif res.outcome != "no_chord":
            harmony.append({"harmony_or_key": "harmony", "time": t, "symbol": res.symbol,
                            "display_mode": res.display_mode, "custom_text": res.custom_text,
                            "comments": res.comments})
    return harmony, unparsed


def cadence_rows(harmonies: list[dict]) -> list[dict]:
    return [{"time": seconds(label_time(r)), "label": r["cadence"], "comments": ""} for r in harmonies if r["cadence"]]


def phrase_spans(harmonies: list[dict], piece_end: Fraction) -> list[tuple[Fraction, Fraction]]:
    """"{" opens, "}" closes, "}{" closes and reopens; a "}" with nothing open closes a phrase that starts where
    the previous one ended (or at the piece's start); one still open at the end closes at the piece's end.
    A "{" while one is open restarts the phrase there."""
    spans, start, last_end = [], None, Fraction(0)
    for r in harmonies:
        mark = r["phraseend"]
        if mark not in ("{", "}", "}{"):
            continue
        t = label_time(r)
        if mark in ("}", "}{"):
            spans.append((last_end if start is None else start, t))
            last_end, start = t, None
        if mark in ("{", "}{"):
            start = t
    if start is not None:
        spans.append((start, piece_end))
    return spans


def phrase_rows(spans) -> list[dict]:
    return [{"start": seconds(a), "end": seconds(b), "level": 1, "label": "", "comments": ""} for a, b in spans]


@dataclass
class Movement:
    id: str
    csvs: dict[str, tuple[list[str], list[dict]]]  # file name -> (fields, rows)
    media_length: Fraction
    source_rows: dict[str, int]
    metadata: dict[str, str]


def movement_metadata(piece: str, row: dict) -> dict[str, str]:
    title = f"{row['workTitle']}, {row['workNumber'][:1]}. {row['workNumber'][1:]}, movement {row['movementNumber']}"
    if row["movementTitle"]:
        title += f": {row['movementTitle']}"
    people = [f"Annotated by {row['annotators']}." if row["annotators"] else "",
              f"Reviewed by {row['reviewers']}." if row["reviewers"] else ""]
    notes = (f"Analysis of {piece} from {CORPUS}, licensed {LICENCE}. Please cite: {CITATION}. "
             f"{' '.join(p for p in people if p)} "
             f"Converted to TiLiA. There is no recording; time unit: {TIME_UNIT}.")
    return {"title": title, "composer": "Wolfgang Amadeus Mozart", "corpus": CORPUS, "licence": LICENCE,
            "time unit": TIME_UNIT, "notes": notes}


def build_movement(piece: str, harmonies: list[dict], measures: list[dict], meta_row: dict) -> Movement:
    bars = read_bars(measures)
    end = bars[-1].end
    harmony, unparsed = harmony_layers(harmonies)
    spans = phrase_spans(harmonies, end)
    cadences = cadence_rows(harmonies)
    csvs = {
        "measures.csv": (BEAT_FIELDS, beat_rows(bars)),
        "harmony.csv": (HARMONY_FIELDS, harmony),
        "cadences.csv": (MARKER_FIELDS, cadences),
        "chords-unparsed.csv": (MARKER_FIELDS, unparsed),
        "phrases.csv": (PHRASE_FIELDS, phrase_rows(spans)),
    }
    source_rows = {
        "Measures": len(bars),
        "Harmony/keys": sum(1 for i, r in enumerate(harmonies) if i == 0 or r["localkey"] != harmonies[i - 1]["localkey"]),
        "Harmony/chords": sum(1 for r in harmonies if r["chord"] not in ("", "@none")),
        "Cadences": len(cadences),
        "Phrases": len(spans),
    }
    return Movement(piece, csvs, end, source_rows, movement_metadata(piece, meta_row))


def write_csvs(movement: Movement, out: Path) -> Path:
    folder = out / "csv" / movement.id
    folder.mkdir(parents=True, exist_ok=True)
    for name, (fields, rows) in movement.csvs.items():
        with open(folder / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return folder


# --------------------------------------------------------------------------- the TiLiA script
def _q(value: str) -> str:
    """A value for TiLiA's command line, which splits on single spaces and has no escapes."""
    return '"' + " ".join(str(value).replace('"', "'").split()) + '"'


def write_script(movement: Movement, csv_dir: Path, tla_path: Path) -> str:
    """The text of the TiLiA script for one movement. Only this function depends on how TiLiA is driven."""
    lines = [f"metadata set {_q(k)} {_q(v)}" for k, v in movement.metadata.items()]
    lines += [
        f"metadata set-media-length {float(movement.media_length)!r}",
        'timelines add beat --name "Measures" --beat-pattern 1',
        'timelines add hierarchy --name "Phrases"',
        'timelines add harmony --name "Harmony"',
        'timelines add marker --name "Cadences"',
        'timelines add marker --name "Chords (unparsed)"',
    ]
    imports = [("beat", "Measures", "measures.csv"), ("hierarchy", "Phrases", "phrases.csv"),
               ("harmony", "Harmony", "harmony.csv"), ("marker", "Cadences", "cadences.csv"),
               ("marker", "Chords (unparsed)", "chords-unparsed.csv")]
    for kind, name, file in imports:
        if not movement.csvs[file][1]:
            continue  # nothing to import; the timeline stays empty
        path = Path(csv_dir) / file
        if kind == "beat":
            lines.append(f"timelines import beat --target-name {_q(name)} --file {path}")
        else:
            lines.append(f"timelines import {kind} by-time --target-name {_q(name)} --file {path}")
    lines.append(f"save {tla_path} --overwrite")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- counting the saved files
def count_tla(path) -> dict[str, int]:
    """Components per layer in a saved .tla file."""
    data = json.loads(Path(path).read_text())
    by_name = {t.get("name"): t for t in data["timelines"].values()}

    def comps(name):
        c = by_name[name].get("components", {})
        return list(c.values()) if isinstance(c, dict) else list(c)

    harmony = comps("Harmony")
    return {
        "Measures": len(by_name["Measures"].get("beats_in_measure") or []),
        "Harmony/keys": sum(1 for c in harmony if "quality" not in c),
        "Harmony/chords": sum(1 for c in harmony if "quality" in c) + len(comps("Chords (unparsed)")),
        "Cadences": len(comps("Cadences")),
        "Phrases": len(comps("Phrases")),
    }


def convert(pieces, out: Path, *, files=None, run_tilia=True, jobs: int = 4) -> dict:
    """Write CSVs, scripts and (with ``run_tilia``) .tla files for ``pieces``; returns the summary.

    TiLiA runs in separate processes, ``jobs`` at a time; the summary keeps the order of ``pieces``.
    """
    out = Path(out)
    files = files or fetch_sources(pieces)
    meta = read_metadata(files["metadata.tsv"])
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    (out / "tla").mkdir(parents=True, exist_ok=True)
    movements, scripts = {}, {}
    for piece in pieces:
        movement = build_movement(piece, read_tsv(files[f"harmonies/{piece}.harmonies.tsv"]),
                                  read_tsv(files[f"measures/{piece}.measures.tsv"]), meta[piece])
        csv_dir = write_csvs(movement, out).resolve()
        tla = (out / "tla" / f"{piece}.tla").resolve()
        scripts[piece] = out / "scripts" / f"{piece}.txt"
        scripts[piece].write_text(write_script(movement, csv_dir, tla), encoding="utf-8")
        movements[piece] = movement
    if not run_tilia:
        return {}

    def run(piece):
        run_script(scripts[piece], check=True)
        counted = count_tla((out / "tla" / f"{piece}.tla").resolve())
        print(f"{piece}: {counted}", flush=True)
        return piece, counted

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        counts = dict(pool.map(run, pieces))
    summary = {piece: {layer: {"components": counts[piece][layer], "source_rows": movements[piece].source_rows[layer]}
                       for layer in LAYERS} for piece in pieces}
    for piece in pieces:
        summary[piece]["lint"] = lint(out / "tla" / f"{piece}.tla", [out / "csv" / piece / "harmony.csv"])
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def package(out: Path, package_dir: Path) -> Path:
    """Zip the .tla files of ``out`` without their file and media paths, with LICENSE and NOTICE.md."""
    out = Path(out)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        files = []
        for tla in sorted((out / "tla").glob("*.tla")):
            data = json.loads(tla.read_text())
            data["file_path"] = ""
            data["media_path"] = ""
            target = Path(tmp) / tla.name
            target.write_text(json.dumps(data), encoding="utf-8")
            files.append(target)
        return build_package(PACKAGE_NAME, files, LICENCE_ID, (HERE / "NOTICE.md").read_text(encoding="utf-8"),
                             out_dir=package_dir)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", nargs="+", metavar="ID", help="movements to convert, e.g. K279-1 (default: all 54)")
    ap.add_argument("--package", type=Path, metavar="DIR", help="also build the zip package in DIR")
    ap.add_argument("--jobs", type=int, default=4, help="TiLiA processes at a time")
    ap.add_argument("--no-tilia", action="store_true", help="write the CSVs and scripts only")
    args = ap.parse_args(argv)
    pieces = args.only or PIECES
    unknown = [p for p in pieces if p not in PIECES]
    if unknown:
        ap.error(f"unknown movement(s): {', '.join(unknown)}")
    convert(pieces, args.out, run_tilia=not args.no_tilia, jobs=args.jobs)
    if args.package:
        if args.no_tilia:
            ap.error("--package needs the .tla files: drop --no-tilia")
        print(package(args.out, args.package))


if __name__ == "__main__":
    main()
