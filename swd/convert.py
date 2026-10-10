"""Convert the Schubert Winterreise Dataset (SWD) v2.1 into TiLiA files, one per song and performance.

    python swd/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia] [--audio]

Run it with the repository root on PYTHONPATH. See swd/README.md.
"""
import argparse
import csv
import functools
import io
import json
import shutil
import sys
import wave
import zipfile
from pathlib import Path

from common.download import _cache_path, _md5, default_cache_dir, fetch_member
from common.package import build_package
from common.runner import ScriptError, run_script
from format_converters.harmony import translate_chord, translate_key
from swd import spelling
from swd.download import fetch_resumable

ARCHIVE_URL = "https://zenodo.org/records/10839767/files/Schubert_Winterreise_Dataset_v2-1.zip?download=1"
ARCHIVE_MD5 = "591c377c6d3db522fd159b8b70180978"
HERE = Path(__file__).resolve().parent
# md5 of every archive member the converter reads, so that single members can be downloaded and checked
MEMBER_MD5 = json.loads((HERE / "members.json").read_text())

PERFORMERS = {
    "AL98": "AL98",
    "FI55": "FI55",
    "FI66": "FI66",
    "FI80": "FI80",
    "HU33": "Hüsch (HU33)",
    "OL06": "OL06",
    "QU98": "QU98",
    "SC06": "Randall Scarlata, baritone, and Jeremy Denk, piano (SC06)",
    "TR99": "TR99",
}
SONGS = [f"{n:02d}" for n in range(1, 25)]
HAS_RECORDING = ("HU33", "SC06")
PACKAGE_NAME = "swd-v2.1-tilia"
LICENCE = "CC-BY-3.0"
CORPUS = "Schubert Winterreise Dataset (SWD), version 2.1, doi:10.5281/zenodo.10839767"
NOTES = (
    "Schubert Winterreise Dataset (SWD) v2.1, doi:10.5281/zenodo.10839767, by Christof Weiß, Frank Zalkow, "
    "Vlora Arifi-Müller, Meinard Müller, Hendrik Vincent Koops, Anja Volk and Harald G. Grohganz. "
    "Licence CC BY 3.0. Measures, structure, chords and keys are the dataset's annotations of this performance, "
    "converted for TiLiA; bar numbers are those printed in the IMSLP (Peters) score. Chords and keys are spelled "
    "as the dataset's score annotations spell them, transposed to the performance; Roman numerals read against "
    "annotator 1's local keys."
)
LAYERS = ["Measures", "Structure", "Harmony/keys", "Harmony/chords",
          "Local keys (ann1)", "Local keys (ann2)", "Local keys (ann3)"]
NO_CHORD = {"N", "X", ""}
ANNOTATORS = (1, 2, 3)
KEY_ANNOTATOR = 1  # whose local keys are on the Harmony timeline, so that the Roman numerals read against them

CHORD_COLUMNS = ["harmony_or_key", "time", "symbol", "display_mode", "custom_text", "comments"]


def item_ids(only=None):
    ids = [f"Schubert_D911-{s}_{p}" for s in SONGS for p in PERFORMERS]
    if only:
        unknown = [i for i in only if i not in ids]
        if unknown:
            raise SystemExit(f"unknown item(s): {' '.join(unknown)}")
        return list(only)
    return ids


def split_id(item):
    work, performer = item.rsplit("_", 1)
    return work, performer, work.rsplit("-", 1)[1]


# ------------------------------------------------------------------ sources
class Source:
    """Reads archive members, from the whole archive when it is at hand, else one by one."""

    def __init__(self, archive=None):
        self.zip = zipfile.ZipFile(archive) if archive else None
        self.archive = Path(archive) if archive else None

    @classmethod
    def open(cls, cache_dir=None):
        """The cached whole archive if there is one; otherwise members are fetched singly."""
        cached = _cache_path(cache_dir, ARCHIVE_URL, ARCHIVE_MD5, "Schubert_Winterreise_Dataset_v2-1.zip")
        if cached.exists() and _md5(cached) == ARCHIVE_MD5:
            return cls(cached)
        return cls()

    def read(self, member) -> bytes:
        if self.zip is not None:
            return self.zip.read(member)
        return fetch_member(ARCHIVE_URL, member, MEMBER_MD5[member]).read_bytes()

    def rows(self, member):
        text = self.read(member).decode("utf-8")
        return list(csv.DictReader(io.StringIO(text), delimiter=";"))

    def extract(self, member, cache_dir=None) -> Path:
        """A member of the whole archive as a file in the cache (for recordings); needs the archive."""
        if self.zip is None:
            raise RuntimeError("recordings are read from the whole archive; download it first (convert.ipynb)")
        info = self.zip.getinfo(member)
        target = Path(cache_dir or default_cache_dir()) / "swd-v2.1" / member
        if not target.exists() or target.stat().st_size != info.file_size:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".part")
            with self.zip.open(member) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            tmp.replace(target)
        return target


def song_titles(source):
    return {r["WorkID"]: r["Title"] for r in source.rows("03_ExtraMaterial/ann_score_overview.csv")}


def global_keys(source):
    return {(r["WorkID"], r["PerformanceID"]): r["key"] for r in source.rows("02_Annotations/ann_audio_globalkey.csv")}


# ------------------------------------------------------------------ the item's data
def read_item(source, item, titles=None, keys=None):
    """Everything one item needs, as read from the source files."""
    work, performer, song = split_id(item)
    a = "02_Annotations/"
    titles = titles or song_titles(source)
    keys = keys or global_keys(source)
    return {
        "item": item, "work": work, "performer": performer, "song": song,
        "title": titles[work],
        "globalkey": keys[(work, performer)],
        "measure": source.rows(f"{a}ann_audio_measure/{item}.csv"),
        "printed": source.rows(f"{a}ann_score-IMSLP_measure/{work}.csv"),
        "structure": source.rows(f"{a}ann_audio_structure/{item}.csv"),
        "chord": source.rows(f"{a}ann_audio_chord/{item}.csv"),
        "score_chord": source.rows(f"{a}ann_score_chord/{work}.csv"),
        "localkey": {n: source.rows(f"{a}ann_audio_localkey-ann{n}/{item}.csv") for n in ANNOTATORS},
    }


def printed_numbers(data):
    """Printed (IMSLP) bar number of each row of the audio measure file.

    Row k of the audio file takes the number of row k of the score's list of bars, which unfolds
    repeats: a pickup (0.750 in the audio file) is bar 0 there. The last audio row is the end of the
    last bar, not a bar of its own; it gets the number after the last printed one.
    """
    printed = [int(r["measure"]) for r in data["printed"]]
    rows = data["measure"]
    if len(rows) != len(printed) + 1:
        raise ValueError(f"{data['item']}: {len(rows)} audio measure rows for {len(printed)} score bars")
    return printed + [printed[-1] + 1]


def chord_start(row):
    return row["start"].strip()


@functools.lru_cache(maxsize=None)
def _translate(label, key):
    return translate_chord(label, "harte", key)


@functools.lru_cache(maxsize=None)
def _key(label):
    return translate_key(label, "harte")


def is_chord(row):
    return row["shorthand"].strip() not in NO_CHORD


def respelled(data):
    """The item's chords and keys spelled from the score (see swd/spelling.py).

    Returns the chord labels (one per row of the chord file, None for N and X), the global key, each
    annotator's local keys (rows with the key replaced), and the semitones by which an annotator's keys were
    moved to agree with the chords (0 except for two annotators in D911-06 and D911-22).
    """
    score = [spelling.parse(r["shorthand"]) for r in data["score_chord"]]
    performance = [spelling.parse(r["shorthand"]) for r in data["chord"]]
    interval = spelling.transposition(score, spelling.chord_shift(score, performance, data["item"]))
    labels = [spelling.respell(c, interval) if c else None for c in score]
    spelled = spelling.spellings([spelling.parse(l) for l in labels if l])
    timed = [(float(r["start"]), p) for r, p in zip(data["chord"], performance)]

    def key(label, offset=0):
        tonic, mode = label.strip().split(":")
        return spelling.key_label((spelling.pitch_class(tonic) + offset) % 12, mode, spelled)

    local, offsets = {}, {}
    for n in ANNOTATORS:
        offsets[n] = spelling.key_offset(data["localkey"][n], timed)
        local[n] = [dict(r, key=key(r["key"], offsets[n])) for r in data["localkey"][n]]
    global_key = key(data["globalkey"])
    # a key written enharmonically (F-sharp minor for G-flat minor) takes the chords in it along
    moves = {k: spelling.enharmonic_shift(k, spelled)
             for k in {global_key, *(r["key"] for r in local[KEY_ANNOTATOR])}}
    return {"chords": labels, "globalkey": global_key, "localkey": local, "offsets": offsets,
            "moves": {k: v for k, v in moves.items() if v is not None}}


def key_rows(data, keys, global_key):
    """The keys of the Harmony timeline: the annotator's, and the global key where a chord falls outside them."""
    spans = [(float(r["start"]), float(r["end"])) for r in keys]
    rows = [(r["start"], r["key"]) for r in keys]
    covered = True
    for r in data["chord"]:
        if not is_chord(r):
            continue
        t = float(chord_start(r))
        inside = any(start <= t < end for start, end in spans)
        if not inside and covered:
            rows.append((chord_start(r), global_key))
        covered = inside
    return sorted(rows, key=lambda r: float(r[0]))


def key_in_force(rows, time):
    current = rows[0][1]
    for start, key in rows:
        if float(start) <= time:
            current = key
    return current


def build_tables(data):
    """The CSV tables of an item: name -> (header, rows)."""
    numbers = printed_numbers(data)
    measures = [[r["start"], numbers[i], "true"] for i, r in enumerate(data["measure"])]

    structure = [[r["start"], r["end"], 1, r["structure"], ""] for r in data["structure"]]

    spelled = respelled(data)
    keys = key_rows(data, spelled["localkey"][KEY_ANNOTATOR], spelled["globalkey"])
    harmony = [["key", t, _key(k), "letter", "", ""] for t, k in keys]
    unparsed = []
    for r, label in zip(data["chord"], spelled["chords"]):
        if not is_chord(r):
            continue
        key = key_in_force(keys, float(chord_start(r)))
        if key in spelled["moves"]:
            label = spelling.respell(spelling.parse(label), spelled["moves"][key])
        res = _translate(label, _key(key))
        if res.outcome == "none":
            unparsed.append([chord_start(r), label, res.comments])
        else:
            # letter symbols carry the spelling; shown as Roman numerals, like BPSD's and DCML's chords
            mode = "roman" if res.display_mode == "letter" else res.display_mode
            harmony.append(["harmony", chord_start(r), res.symbol, mode, res.custom_text, res.comments])
    # a key and a chord at the same time: the key first, so that the chord reads against it
    harmony.sort(key=lambda row: (float(row[1]), row[0] != "key"))

    tables = {
        "measures": (["time", "measure", "is_first_in_measure"], measures),
        "structure": (["start", "end", "level", "label", "comments"], structure),
        "harmony": (CHORD_COLUMNS, harmony),
        "unparsed": (["time", "label", "comments"], unparsed),
    }
    for n in ANNOTATORS:
        rows = [["key", r["start"], _key(r["key"]), "letter", "", ""] for r in spelled["localkey"][n]]
        tables[f"localkeys-ann{n}"] = (CHORD_COLUMNS, rows)
    return tables


def write_tables(tables, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (header, rows) in tables.items():
        paths[name] = folder / f"{name}.csv"
        with open(paths[name], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
    return paths


def media_length(data):
    """Latest time any annotation mentions, in seconds."""
    times = [float(r["start"]) for r in data["measure"]]
    for r in data["structure"] + data["chord"]:
        times.append(float(r["end"]))
    for rows in data["localkey"].values():
        times += [float(r["end"]) for r in rows]
    return max(times)


def metadata(data):
    n = int(data["song"])
    values = {
        "title": f"Winterreise, D 911: {n}. {data['title']}",
        "composer": "Franz Schubert",
        "performer": PERFORMERS[data["performer"]],
        "corpus": CORPUS,
        "licence": "CC BY 3.0",
        "notes": NOTES,
    }
    return {k: v.replace('"', "'") for k, v in values.items()}


def write_script(data, paths, tla, recording=None):
    """The TiLiA command script of an item. When TiLiA gets a non-interactive `tilia run`, only this changes."""
    lines = [f'metadata set "{k}" "{v}"' for k, v in metadata(data).items()]
    if recording:
        lines.append(f"load-media {recording}")
        # an annotation may end a few milliseconds after the recording does, and TiLiA refuses times past the media
        with wave.open(str(recording)) as w:
            duration = w.getnframes() / w.getframerate()
        if media_length(data) > duration:
            lines.append(f"metadata set-media-length {media_length(data)}")
    else:
        lines.append(f"metadata set-media-length {media_length(data)}")
    lines += [
        'timelines add beat --name "Measures" --beat-pattern 1',
        'timelines add hierarchy --name "Structure"',
        'timelines add harmony --name "Harmony"',
    ]
    lines += [f'timelines add harmony --name "Local keys (ann{n})"' for n in ANNOTATORS]
    lines.append('timelines add marker --name "Chords (unparsed)"')
    lines.append(f'timelines import beat --target-name "Measures" --file {paths["measures"]}')
    lines.append(f'timelines import hierarchy by-time --target-name "Structure" --file {paths["structure"]}')
    lines.append(f'timelines import harmony by-time --target-name "Harmony" --file {paths["harmony"]}')
    for n in ANNOTATORS:
        lines.append(f'timelines import harmony by-time --target-name "Local keys (ann{n})" '
                     f'--file {paths[f"localkeys-ann{n}"]}')
    lines.append(f'timelines import marker by-time --target-name "Chords (unparsed)" --file {paths["unparsed"]}')
    lines.append(f"save {tla} --overwrite")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ reading the saved files
def count_tla(path):
    """Components per layer, counted in the saved .tla file."""
    timelines = {t["name"]: t for t in json.loads(Path(path).read_text())["timelines"].values() if "name" in t}

    def comps(name):
        c = timelines[name].get("components", {})
        return list(c.values()) if isinstance(c, dict) else c

    keys = lambda name: sum(1 for c in comps(name) if "type" in c and "quality" not in c)
    out = {
        "Measures": len(timelines["Measures"].get("beats_in_measure") or []),
        "Structure": len(comps("Structure")),
        "Harmony/keys": keys("Harmony"),
        "Harmony/chords": sum(1 for c in comps("Harmony") if "quality" in c) + len(comps("Chords (unparsed)")),
    }
    for n in ANNOTATORS:
        out[f"Local keys (ann{n})"] = keys(f"Local keys (ann{n})")
    return out


def source_rows(data):
    spelled = respelled(data)
    keys = key_rows(data, spelled["localkey"][KEY_ANNOTATOR], spelled["globalkey"])
    out = {"Measures": len(data["measure"]), "Structure": len(data["structure"]), "Harmony/keys": len(keys),
           "Harmony/chords": sum(1 for r in data["chord"] if is_chord(r))}
    for n in ANNOTATORS:
        out[f"Local keys (ann{n})"] = len(data["localkey"][n])
    return out


# ------------------------------------------------------------------ the run
def run_script_retrying(script, attempts=3):
    """Run a script through TiLiA; a failed run (seen once, after loading a recording) is repeated from scratch."""
    for attempt in range(attempts):
        try:
            return run_script(script, check=True)
        except ScriptError:
            if attempt == attempts - 1:
                raise


def convert_item(source, item, out, *, tilia=True, audio=False, titles=None, keys=None):
    """Write the CSVs and the script of one item, run TiLiA, and return its summary entry (None without TiLiA)."""
    out = Path(out)
    data = read_item(source, item, titles, keys)
    paths = write_tables(build_tables(data), out / "csv" / item)
    (out / "scripts").mkdir(exist_ok=True)
    (out / "tla").mkdir(exist_ok=True)
    tla = (out / "tla" / f"{item}.tla").resolve()
    recording = None
    if audio and data["performer"] in HAS_RECORDING:
        recording = source.extract(f"01_RawData/audio_wav/{item}.wav").resolve()
    script = out / "scripts" / f"{item}.txt"
    script.write_text(write_script(data, {k: v.resolve() for k, v in paths.items()}, tla, recording))
    if not tilia:
        return None
    run_script_retrying(script)
    counts, rows = count_tla(tla), source_rows(data)
    entry = {layer: {"components": counts[layer], "source_rows": rows[layer]} for layer in LAYERS}
    moved = {f"Local keys (ann{n})": o for n, o in respelled(data)["offsets"].items() if o}
    if moved:
        entry["keys_moved_to_the_chords"] = moved  # semitones
    return entry


def convert_all(source, out, ids, *, tilia=True, audio=False, log=print):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    titles, keys = song_titles(source), global_keys(source)
    summary = {}
    for i, item in enumerate(ids, 1):
        entry = convert_item(source, item, out, tilia=tilia, audio=audio, titles=titles, keys=keys)
        if entry is not None:
            summary[item] = entry
        log(f"[{i}/{len(ids)}] {item}")
    if tilia:
        (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def package(out, package_dir):
    """Zip the .tla files of ``out`` without media or file paths, with LICENSE and NOTICE.md."""
    out, package_dir = Path(out), Path(package_dir)
    staging = package_dir / "staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    files = []
    for tla in sorted((out / "tla").glob("*.tla")):
        data = json.loads(tla.read_text())
        data["file_path"] = ""
        data["media_path"] = ""
        copy = staging / tla.name
        copy.write_text(json.dumps(data))
        files.append(copy)
    zip_path = build_package(PACKAGE_NAME, files, LICENCE, (HERE / "NOTICE.md").read_text(), out_dir=package_dir)
    shutil.rmtree(staging)
    return zip_path


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", required=True, help="output folder: csv/, scripts/, tla/, summary.json")
    p.add_argument("--only", nargs="+", metavar="ID", help="items to convert, e.g. Schubert_D911-01_HU33")
    p.add_argument("--package", metavar="DIR", help="build the zip package in DIR")
    p.add_argument("--no-tilia", action="store_true", help="write the CSVs and scripts only")
    p.add_argument("--audio", action="store_true",
                   help="load the recordings of HU33 and SC06 (needs the whole archive, which is downloaded)")
    args = p.parse_args(argv)
    ids = item_ids(args.only)
    if args.audio:
        source = Source(fetch_resumable(ARCHIVE_URL, ARCHIVE_MD5))
    else:
        source = Source.open()
    convert_all(source, args.out, ids, tilia=not args.no_tilia, audio=args.audio)
    if args.package:
        if args.no_tilia:
            raise SystemExit("--package needs the .tla files: leave out --no-tilia")
        print(package(args.out, args.package))


if __name__ == "__main__":
    sys.exit(main())
