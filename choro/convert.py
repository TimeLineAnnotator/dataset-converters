"""Convert the Choro Songbook Corpus (DCMLab/choro, v1.3.3) into TiLiA files, one per piece.

    python choro/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia]

There is no recording: one second stands for one quarter note (the quarter-second convention).
The corpus's table lists the chords in the order the piece is played (repeats written out), each with
its duration, so a chord's time is the sum of the durations before it.
"""
import argparse
import csv
import functools
import io
import itertools
import json
import re
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from common.download import fetch  # noqa: E402
from common.package import build_package  # noqa: E402
from common.runner import ScriptError, run_script  # noqa: E402

ZIP_URL = "https://zenodo.org/records/21219604/files/DCMLab/choro-v1.3.3.zip?download=1"
ZIP_MD5 = "0f8a0dadb52577fd3c51ef82daf31bdb"
ZIP_ROOT = "DCMLab-choro-e7e6e6a/data/"
PACKAGE_NAME = "choro-v1.3.3-tilia"
LICENCE_ID = "CC-BY-NC-SA-4.0"
LICENCE = "CC BY-NC-SA 4.0"
CORPUS = "Choro Songbook Corpus (DCMLab/choro), v1.3.3, DOI 10.5281/zenodo.21219604"
TIME_UNIT = "quarter notes (no recording: one second stands for one quarter note)"
AUTHORS = "Fabian C. Moss, Willian Fernandes de Souza and Martin A. Rohrmeier"
CITATION = (
    "Moss, F. C., Fernandes de Souza, W. and Rohrmeier, M. (2020) Harmony and form in Brazilian Choro: "
    "A corpus-driven approach to musical style analysis. Journal of New Music Research, 49(5), 416-437. "
    "https://doi.org/10.1080/09298215.2020.1797109"
)
SOURCE = "Chediak, A., Sève, M., Souza, R. and Dininho (eds.) (2009, 2011) Choro Songbook, vols. 1-3. Lumiar Editora"

LAYERS = ("Measures", "Harmony/keys", "Harmony/chords", "Parts", "Phrases")

BEAT_FIELDS = ["time", "measure", "is_first_in_measure"]
HARMONY_FIELDS = ["harmony_or_key", "time", "symbol", "display_mode", "custom_text", "comments"]
MARKER_FIELDS = ["time", "label", "comments"]
FORM_FIELDS = ["start", "end", "level", "label", "comments"]

NO_CHORD = "N"


# --------------------------------------------------------------------------- reading the source
def fetch_corpus(cache_dir=None) -> Path:
    return fetch(ZIP_URL, ZIP_MD5, cache_dir=cache_dir)


@dataclass
class Piece:
    id: str  # the transcription's file name without ".txt"
    rows: list[dict]
    transcription: str


def read_corpus(zip_path) -> dict[str, Piece]:
    """id -> Piece, in the table's order. Transcriptions without rows in the table are left out."""
    with zipfile.ZipFile(zip_path) as z:
        text = z.read(ZIP_ROOT + "choro.tsv").decode("utf-8")
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text), delimiter="\t")]
        pieces = {}
        for filename, group in itertools.groupby(rows, key=lambda r: r["filename"]):
            pid = filename.removesuffix(".txt")
            if pid in pieces:
                raise ValueError(f"{filename}: its rows are not contiguous in choro.tsv")
            transcription = z.read(ZIP_ROOT + "transcriptions/" + filename).decode("utf-8")
            pieces[pid] = Piece(pid, list(group), transcription)
    return pieces


def seconds(q: Fraction) -> str:
    return repr(float(q))


def quarters(row: dict) -> Fraction:
    """The table's `duration` is in whole notes (0.5 is a 2/4 bar), whatever its README says."""
    return 4 * Fraction(row["duration"])


def meter(text: str) -> tuple[int, int]:
    """`local_meter` is written as a Python tuple, "(2, 4)"."""
    m = re.fullmatch(r"\((\d+),\s*(\d+)\)", text)
    if not m:
        raise ValueError(f"not a meter: {text!r}")
    return int(m.group(1)), int(m.group(2))


def chord_times(rows: list[dict]) -> list[Fraction]:
    times, t = [], Fraction(0)
    for r in rows:
        times.append(t)
        t += quarters(r)
    return times + [t]


# --------------------------------------------------------------------------- bars
@dataclass
class Bar:
    number: int
    start: Fraction
    actual: Fraction  # sum of its chords' durations, in quarter notes
    numerator: int
    denominator: int

    @property
    def nominal(self) -> Fraction:
        return Fraction(4 * self.numerator, self.denominator)

    @property
    def n_beats(self) -> int:
        return max(1, round(self.numerator * self.actual / self.nominal))


def read_bars(rows: list[dict], times: list[Fraction]) -> list[Bar]:
    """A bar starts at its first chord. The table numbers bars in playing order, from 1, without gaps."""
    bars: dict[int, Bar] = {}
    for r, t in zip(rows, times):
        n = int(r["bar_no"])
        if n not in bars:
            bars[n] = Bar(n, t, Fraction(0), *meter(r["local_meter"]))
        bars[n].actual += quarters(r)
    if list(bars) != list(range(1, len(bars) + 1)):
        raise ValueError("bar numbers are not 1, 2, 3, ... in order")
    return list(bars.values())


def beat_rows(bars: list[Bar]) -> list[dict]:
    """numerator beats per bar over its nominal length; a bar of another length gets
    round(numerator x actual / nominal) of them, at least one."""
    rows = []
    for bar in bars:
        step = bar.nominal / bar.numerator
        for i in range(bar.n_beats):
            rows.append({"time": seconds(bar.start + i * step), "measure": bar.number,
                         "is_first_in_measure": "true" if i == 0 else "false"})
    return rows


def irregular_bars(bars: list[Bar]) -> list[int]:
    """Bars whose chords don't add up to the time signature (transcription slips in the source)."""
    return [b.number for b in bars if b.actual != b.nominal]


# --------------------------------------------------------------------------- harmony
_PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_STEP_PC = [0, 2, 4, 5, 7, 9, 11]

# A triad over its minor seventh has exactly the notes of the seventh chord in third inversion
# ("D/C" is D7/C). Translated as written, the shared translator approximates it by a power chord.
_SLASH_SEVENTH = {"maj/b7": "7/b7", "min/b7": "min7/b7"}


def harte_key(local_key: str) -> str:
    """The table's keys ("F", "Dm", "F#m", "Bb") as Harte keys ("F:maj", "D:min")."""
    m = re.fullmatch(r"([A-G][#b]*)(m?)", local_key)
    if not m:
        raise ValueError(f"not a key: {local_key!r}")
    return f"{m.group(1)}:{'min' if m.group(2) else 'maj'}"


@functools.lru_cache(maxsize=None)
def tilia_key(local_key: str) -> str:
    from format_converters.harmony import translate_key

    return translate_key(harte_key(local_key), "harte")


def pitch_class(name: str) -> int:
    return (_PITCH[name[0]] + name.count("#") - name.count("b")) % 12


def stored_root(params: dict) -> int:
    return (_STEP_PC[params["step"]] + params["accidental"]) % 12


_LETTERS = "CDEFGAB"
_SPELLED = re.compile(r"([A-G])([#b]*)$")


def label_bass(label: str) -> str | None:
    """The bass note of a transcribed slash chord ("Eb7/Bb" -> "Bb"), or None."""
    head, sep, bass = label.rpartition("/")
    return bass if sep and head and _SPELLED.match(bass) else None


def bass_degree(root: str, bass: str) -> str | None:
    """The Harte degree of `bass` above `root`, spelled as the notes are ("Eb", "Bb" -> "5"; "C", "G#" -> "#5")."""
    r, b = _SPELLED.match(root), _SPELLED.match(bass)
    number = (_LETTERS.index(b.group(1)) - _LETTERS.index(r.group(1))) % 7
    alteration = (pitch_class(bass) - pitch_class(root) - _STEP_PC[number] + 6) % 12 - 6
    if abs(alteration) > 2:
        return None
    return ("#" * alteration if alteration > 0 else "b" * -alteration) + str(number + 1)


def harte_bass(harte: str) -> int:
    root, _, rest = harte.partition(":")
    degree = rest.rpartition("/")[2] if "/" in rest else "1"
    m = re.fullmatch(r"([#b]*)(\d+)", degree)
    if not m:
        raise ValueError(f"not a Harte bass degree: {harte!r}")
    return (pitch_class(root) + _STEP_PC[(int(m.group(2)) - 1) % 7] + m.group(1).count("#") - m.group(1).count("b")) % 12


def checked_harte(label: str, harte: str) -> tuple[str, str]:
    """(Harte label, problem). Where the table's Harte label has another bass than the chord as transcribed
    ("Eb7/Bb" as "Eb:7/b5"), the transcribed bass wins, spelled as written."""
    # the table writes a major seventh among the added tones as "7M", which isn't Harte: "F:min(7M,9)"
    harte = re.sub(r"(?<=[(,])7M(?=[,)])", "7", harte)
    bass = label_bass(label)
    if harte == NO_CHORD or bass is None or harte_bass(harte) == pitch_class(bass):
        return harte, ""
    root, _, rest = harte.partition(":")
    degree = bass_degree(root, bass)
    if degree is None:
        return harte, f"{label}: the table's Harte label {harte} has another bass, kept"
    fixed = f"{root}:{rest.rpartition('/')[0] if '/' in rest else rest}/{degree}"
    return fixed, f"{label}: the table's Harte label {harte} has another bass; read as {fixed}"


def without_extensions(harte: str) -> str:
    """"D:7(b9)/3" -> "D:7/3": the chord without the tones in brackets."""
    return re.sub(r"\([^)]*\)", "", harte)


@dataclass(frozen=True)
class Placed:
    """Where a chord goes: the harmony timeline (`symbol` set) or the unparsed markers."""
    symbol: str | None
    display_mode: str = ""
    custom_text: str = ""
    comments: str = ""


def without_bass(harte: str) -> str:
    """"D:7/3" -> "D:7"."""
    root, _, rest = harte.partition(":")
    return f"{root}:{rest.rpartition('/')[0]}" if "/" in rest else harte


def same_quality(chord, without_its_bass) -> bool:
    return without_its_bass is not None and chord.params["quality"] == without_its_bass.params["quality"]


@functools.lru_cache(maxsize=None)
def translate(label: str, harte: str, key: str) -> Placed:
    """A chord of the table (its label as transcribed, its Harte label) under a TiLiA key.

    The shared translator gives the symbol. Only a symbol on the source's root is kept: TiLiA can read the
    notes of C7(b9) as a diminished ninth on B-flat, which has the notes but not the chord. A chord with no
    exact symbol is stored as the first of these that has one, with the label shown as custom text: the
    chord without its bracketed tones, without its bass, without both. Failing those, the translator's
    own approximation on the same root; failing that, the chord goes to the unparsed markers.
    """
    from format_converters.harmony import translate_chord

    root = pitch_class(harte.split(":")[0])
    shorthand = harte.partition(":")[2]
    written = f"{harte.partition(':')[0]}:{_SLASH_SEVENTH[shorthand]}" if shorthand in _SLASH_SEVENTH else harte

    def exact(h):
        res = translate_chord(h, "harte", key)
        return res if res.outcome == "letter" and stored_root(res.params) == root else None

    first = translate_chord(written, "harte", key)
    if first.outcome == "letter" and stored_root(first.params) == root:
        if "/" in shorthand and not same_quality(first, exact(without_bass(harte))):
            # the bass is not in the chord and the symbol names it (D/C as D7/C, Bb/A as Bbmaj7/A)
            return Placed(first.symbol, "custom", label, f"{label} has the notes of {first.symbol}")
        return Placed(first.symbol, first.display_mode)

    if first.outcome in ("letter", "approx"):
        why = f"TiLiA reads these notes as {first.symbol}" if first.outcome == "letter" else "no exact symbol"
    else:
        why = first.comments or "no exact symbol"
    for reduced, what in ((without_extensions(harte), "without its added tones"),
                          (without_bass(harte), "without its bass"),
                          (without_bass(without_extensions(harte)), "without its added tones and bass")):
        if reduced != harte and (res := exact(reduced)):
            return Placed(res.symbol, "custom", label, f"{why}; stored {what} as {res.symbol}")
    if first.outcome == "approx" and stored_root(first.params) == root:
        return Placed(first.symbol, "custom", label, first.comments)
    if first.outcome in ("letter", "approx"):
        return Placed(None, comments=f"TiLiA reads these notes only as {first.symbol}, on another root")
    return Placed(None, comments=why)


def harmony_layers(rows: list[dict], times: list[Fraction]) -> tuple[list[dict], list[dict], list[str]]:
    """(rows of the harmony CSV, rows of the unparsed-chords CSV, problems in the source).
    A key comes before the chord it governs."""
    harmony, unparsed, problems = [], [], []
    previous = None
    for r, t in zip(rows, times):
        key = tilia_key(r["local_key"])
        if r["local_key"] != previous:
            previous = r["local_key"]
            harmony.append({"harmony_or_key": "key", "time": seconds(t), "symbol": key, "display_mode": "letter",
                            "custom_text": "", "comments": ""})
        if r["harte"] == NO_CHORD:
            continue
        harte, problem = checked_harte(r["chord"], r["harte"])
        if problem:
            problems.append(f"bar {r['bar_no']}: {problem}")
        placed = translate(r["chord"], harte, key)
        if placed.symbol is None:
            unparsed.append({"time": seconds(t), "label": r["chord"], "comments": placed.comments})
        else:
            harmony.append({"harmony_or_key": "harmony", "time": seconds(t), "symbol": placed.symbol,
                            "display_mode": placed.display_mode or "letter", "custom_text": placed.custom_text,
                            "comments": placed.comments})
    return harmony, unparsed, problems


# --------------------------------------------------------------------------- parts and phrases
_DEFINITION = re.compile(r"^(\w+)(?:\[[^\]]*\])?\s*:(.*)$", re.M)
_PHRASE = re.compile(r"P\d+$")


def grammar(transcription: str) -> list[tuple[int | None, str, str]]:
    """The piece's phrases in playing order, from the transcription's rules (S: $Intro $PartA ..., PartA:
    $P1 $P2 ...): (which occurrence of a part, or None at the top level; the part; the phrase)."""
    rules = {m.group(1): m.group(2) for m in _DEFINITION.finditer(transcription)}
    out: list[tuple[int | None, str, str]] = []
    occurrence = itertools.count()

    def walk(name, part, occ, depth):
        if depth > 20:
            raise ValueError(f"rule {name!r} nests too deeply")
        for token in re.findall(r"\$(\w+)", rules[name]):
            if _PHRASE.match(token):
                out.append((occ, part, token))
            else:
                walk(token, token, next(occurrence), depth + 1)

    walk("S", "", None, 0)
    return out


@dataclass
class Unit:
    start: Fraction
    end: Fraction
    label: str
    comments: str = ""


def part_label(part: str) -> str:
    return part.removeprefix("Part")


def form_units(piece: Piece, times: list[Fraction]) -> tuple[list[Unit], list[Unit], list[str]]:
    """(parts, phrases, problems). The table's (part, phrase) runs are matched to the rules; a run that the
    rules play two or more times in a row is split into that many equal groups of bars."""
    rows = piece.rows
    runs = []  # (part, phrase, indexes of its rows)
    for key, group in itertools.groupby(range(len(rows)), key=lambda i: (rows[i]["part"], rows[i]["phrase"])):
        runs.append((*key, list(group)))
    tokens = grammar(piece.transcription)
    merged = [(k, list(g)) for k, g in itertools.groupby(tokens, key=lambda t: (t[1], t[2]))]
    if [k for k, _ in merged] != [(p, ph) for p, ph, _ in runs]:
        raise ValueError(f"{piece.id}: the transcription's rules don't match the table's parts and phrases")

    problems = []
    instances = []  # (part occurrence, part, phrase, start, end, comments)
    for (part, phrase, idx), (_, copies) in zip(runs, merged):
        bars = sorted({int(rows[i]["bar_no"]) for i in idx})
        k = len(copies)
        if k > 1 and len(bars) % k:
            problems.append(f"{phrase} is played {k} times in a row over {len(bars)} bars: kept as one unit")
            copies, k = copies[:1], 1
        size = len(bars) // k
        for j, token in enumerate(copies):
            group = set(bars[j * size:(j + 1) * size])
            members = [i for i in idx if int(rows[i]["bar_no"]) in group]
            comment = f"{phrase} played {k} times in a row" if k > 1 else ""
            instances.append((token[0], part, phrase, times[members[0]], times[members[-1] + 1], comment))

    phrases = [Unit(s, e, ph, c) for _, _, ph, s, e, c in instances]
    returns = returned_parts([(occ, part, phrase) for occ, part, phrase, *_ in instances])
    keys = []  # which part unit each phrase belongs to: (part occurrence, part, inferred) or None
    run = itertools.count()
    for (occ, part, *_), returned in zip(instances, returns):
        if occ is not None:
            keys.append((occ, part, False))
        elif returned is None:
            keys.append(None)
            next(run)
        else:
            previous = keys[-1] if keys else None
            same = previous is not None and previous[2] and previous[1] == returned
            keys.append(previous if same else (f"return {next(run)}", returned, True))
    parts = []
    for key, group in itertools.groupby(zip(keys, instances), key=lambda x: x[0]):
        if key is None:
            continue
        group = [inst for _, inst in group]
        label = part_label(key[1])
        comment = (f"The rules play these phrases outside any part; they are phrases of part {label}"
                   if key[2] else "")
        parts.append(Unit(group[0][3], group[-1][4], label, comment))
    return parts, phrases, problems


def returned_parts(tokens: list[tuple[int | None, str, str]]) -> list[str | None]:
    """For each phrase the rules play at the top level (S: ... $PartB $P1 $P2), the part (PartA, PartB, ...)
    whose phrases it repeats, or None; None for the phrases inside parts. A phrase in one part's rule belongs
    to that part. A phrase in several parts' rules belongs to its neighbour's part (the previous phrase's,
    else the next's) when that part has it. Intros, codas and fadeouts are not looked at: a top-level phrase
    that only they play (a vamp before A) stays outside any part, as do phrases in no rule (transitions)."""
    owners: dict[str, set[str]] = {}
    for occ, part, phrase in tokens:
        if occ is not None and part.startswith("Part"):
            owners.setdefault(phrase, set()).add(part)
    out: list[str | None] = []
    for occ, _, phrase in tokens:
        mine = owners.get(phrase, set()) if occ is None else set()
        out.append(next(iter(mine)) if len(mine) == 1 else None)
    for i, (occ, _, phrase) in enumerate(tokens):
        mine = owners.get(phrase, set()) if occ is None else set()
        if len(mine) < 2:
            continue
        neighbours = []
        for j in (i - 1, i + 1):
            if 0 <= j < len(tokens) and tokens[j][0] is None:
                neighbours.append(out[j])
        out[i] = next((n for n in neighbours if n in mine), None)
    return out


def form_rows(parts: list[Unit], phrases: list[Unit]) -> list[dict]:
    rows = [{"start": seconds(u.start), "end": seconds(u.end), "level": 2, "label": u.label, "comments": u.comments}
            for u in parts]
    rows += [{"start": seconds(u.start), "end": seconds(u.end), "level": 1, "label": u.label,
              "comments": u.comments} for u in phrases]
    return rows


# --------------------------------------------------------------------------- one piece
@dataclass
class Converted:
    id: str
    csvs: dict[str, tuple[list[str], list[dict]]]  # file name -> (fields, rows)
    media_length: Fraction
    source_rows: dict[str, int]
    metadata: dict[str, str]
    irregular_bars: list[int] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def piece_metadata(piece: Piece) -> dict[str, str]:
    r = piece.rows[0]
    notes = (f"Chord symbols and form of {r['title']} from {CORPUS}, licensed {LICENCE}, transcribed from "
             f"{SOURCE}. Please cite: {CITATION}. Converted to TiLiA. There is no recording; time unit: {TIME_UNIT}.")
    year = r["year"].removesuffix(".0")
    values = {"title": r["title"], "composer": r["composer"], "composition year": year, "genre": r["sub_genre"],
              "tonality": r["global_key"], "time signature": r["global_meter"],
              "source": f"Choro Songbook, vol. {r['songbook']}", "corpus": CORPUS, "licence": LICENCE,
              # the fields TiLiA's web platform reads for an analysis's author and licence
              "analysis author": AUTHORS, "analysis license": LICENCE,
              "time unit": TIME_UNIT, "notes": notes}
    return {k: v for k, v in values.items() if v}


def build_piece(piece: Piece) -> Converted:
    rows = piece.rows
    times = chord_times(rows)
    bars = read_bars(rows, times)
    harmony, unparsed, problems = harmony_layers(rows, times)
    parts, phrases, form_problems = form_units(piece, times)
    problems += form_problems
    csvs = {
        "measures.csv": (BEAT_FIELDS, beat_rows(bars)),
        "harmony.csv": (HARMONY_FIELDS, harmony),
        "chords-unparsed.csv": (MARKER_FIELDS, unparsed),
        "form.csv": (FORM_FIELDS, form_rows(parts, phrases)),
    }
    source_rows = {
        "Measures": len(bars),
        "Harmony/keys": sum(1 for i, r in enumerate(rows) if i == 0 or r["local_key"] != rows[i - 1]["local_key"]),
        "Harmony/chords": sum(1 for r in rows if r["harte"] != NO_CHORD),
        "Parts": len(parts),
        "Phrases": len(phrases),
    }
    return Converted(piece.id, csvs, times[-1], source_rows, piece_metadata(piece), irregular_bars(bars), problems)


def write_csvs(converted: Converted, out: Path) -> Path:
    folder = out / "csv" / converted.id
    folder.mkdir(parents=True, exist_ok=True)
    for name, (fields, rows) in converted.csvs.items():
        with open(folder / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return folder


# --------------------------------------------------------------------------- the TiLiA script
def _q(value: str) -> str:
    """A value for TiLiA's command line, which splits on single spaces and has no escapes."""
    return '"' + " ".join(str(value).replace('"', "'").split()) + '"'


def write_script(converted: Converted, csv_dir: Path, tla_path: Path) -> str:
    """The text of the TiLiA script for one piece. Only this function depends on how TiLiA is driven."""
    lines = [f"metadata set {_q(k)} {_q(v)}" for k, v in converted.metadata.items()]
    lines += [
        f"metadata set-media-length {float(converted.media_length)!r}",
        'timelines add beat --name "Measures" --beat-pattern 1',
        'timelines add hierarchy --name "Form"',
        'timelines add harmony --name "Harmony"',
        'timelines add marker --name "Chords (unparsed)"',
    ]
    imports = [("beat", "Measures", "measures.csv"), ("hierarchy", "Form", "form.csv"),
               ("harmony", "Harmony", "harmony.csv"), ("marker", "Chords (unparsed)", "chords-unparsed.csv")]
    for kind, name, file in imports:
        if not converted.csvs[file][1]:
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

    harmony, form = comps("Harmony"), comps("Form")
    return {
        "Measures": len(by_name["Measures"].get("beats_in_measure") or []),
        "Harmony/keys": sum(1 for c in harmony if "quality" not in c),
        "Harmony/chords": sum(1 for c in harmony if "quality" in c) + len(comps("Chords (unparsed)")),
        "Parts": sum(1 for c in form if c.get("level") == 2),
        "Phrases": sum(1 for c in form if c.get("level") == 1),
    }


def run_script_retrying(script, pid, attempts=3):
    """Run a script through TiLiA; a run that stops before its first command (TiLiA failing to start, seen
    once in 300 runs) is repeated from scratch."""
    for attempt in range(attempts):
        try:
            return run_script(script, check=True)
        except ScriptError as e:
            if attempt == attempts - 1:
                raise RuntimeError(f"{pid}: TiLiA failed {attempts} times") from e


def convert(ids, out: Path, *, pieces=None, run_tilia=True, jobs: int = 4) -> dict:
    """Write CSVs, scripts and (with ``run_tilia``) .tla files for ``ids``; returns the summary.

    TiLiA runs in separate processes, ``jobs`` at a time; the summary keeps the order of ``ids``.
    """
    out = Path(out)
    pieces = pieces or read_corpus(fetch_corpus())
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    (out / "tla").mkdir(parents=True, exist_ok=True)
    converted, scripts = {}, {}
    for pid in ids:
        c = build_piece(pieces[pid])
        csv_dir = write_csvs(c, out).resolve()
        tla = (out / "tla" / f"{pid}.tla").resolve()
        scripts[pid] = out / "scripts" / f"{pid}.txt"
        scripts[pid].write_text(write_script(c, csv_dir, tla), encoding="utf-8")
        converted[pid] = c
    if not run_tilia:
        return {}

    def run(pid):
        run_script_retrying(scripts[pid], pid)
        counted = count_tla((out / "tla" / f"{pid}.tla").resolve())
        print(f"{pid}: {counted}", flush=True)
        return pid, counted

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        counts = dict(pool.map(run, ids))
    summary = {pid: {layer: {"components": counts[pid][layer], "source_rows": converted[pid].source_rows[layer]}
                     for layer in LAYERS} for pid in ids}
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    report = {pid: {"irregular_bars": c.irregular_bars, "problems": c.problems}
              for pid, c in converted.items() if c.irregular_bars or c.problems}
    (out / "source-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
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
    ap.add_argument("--only", nargs="+", metavar="ID", help="pieces to convert, e.g. 1_alvorada_WF (default: all 295)")
    ap.add_argument("--package", type=Path, metavar="DIR", help="also build the zip package in DIR")
    ap.add_argument("--jobs", type=int, default=4, help="TiLiA processes at a time")
    ap.add_argument("--no-tilia", action="store_true", help="write the CSVs and scripts only")
    args = ap.parse_args(argv)
    pieces = read_corpus(fetch_corpus())
    ids = args.only or list(pieces)
    unknown = [p for p in ids if p not in pieces]
    if unknown:
        ap.error(f"unknown piece(s): {', '.join(unknown)}")
    convert(ids, args.out, pieces=pieces, run_tilia=not args.no_tilia, jobs=args.jobs)
    if args.package:
        if args.no_tilia:
            ap.error("--package needs the .tla files: drop --no-tilia")
        print(package(args.out, args.package))


if __name__ == "__main__":
    main()
