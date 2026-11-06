"""Checks on a converted TiLiA file: the spelling of its keys and chords, and sections that overlap.

    lint(tla_path, harmony_csvs=()) -> {"errors": n, "warnings": n, "rules": {rule: n}, "examples": [...]}

Keys, chord roots and sections are read from the saved .tla file, as TiLiA stores them, whatever the source
wrote (letter symbols or Roman numerals). Slash basses are read from the harmony CSVs, since TiLiA does not keep
a bass that isn't a chord tone. Chords shown as custom text are skipped: their symbol is an approximation that
TiLiA holds, with the source label as the text. So are diminished ninths, which stand for 7-flat-9 chords
until TiLiA has that quality (see SKIPPED_QUALITIES).

Rules (level, name):
- error, numeral-double-accidental: a double flat or sharp in front of the Roman numeral (bbI for VII).
- error, key-signature: a key with more than seven sharps or flats (D-sharp major).
- warning, root-fits-respelled: a root that, named with another letter, would fit the key (A-sharp in D minor
  reads #V; B-flat is VI). Chromatic chords such as bII have no such name, so they pass.
- error, bass-enharmonic: a bass that is a chord tone under another name (C#7/F: E-sharp is the third). TiLiA
  stores it as an added bass note, not as an inversion.
- warning, bass-not-chord-tone: a bass outside the chord (C/D), as some styles write for reading convenience.
- error, section-overlap: two sections at the same level of a hierarchy overlap.
"""
import csv
import functools
import json
from pathlib import Path

import music21

LEVELS = {
    "numeral-double-accidental": "error",
    "key-signature": "error",
    "root-fits-respelled": "warning",
    "bass-enharmonic": "error",
    "bass-not-chord-tone": "warning",
    "section-overlap": "error",
}
STEPS = "CDEFGAB"  # TiLiA's step numbers index this
EXAMPLES = 5
# TiLiA has no 7-flat-9 quality (TimeLineAnnotator/desktop#714), so the translator stores one as a diminished ninth
# a major third below its root (C7b9/E as A#o9/E). Its root is wrong by construction; skipped until TiLiA has the quality.
SKIPPED_QUALITIES = {"diminished-ninth"}
TOLERANCE = 0.002  # seconds: sources round times to the millisecond


SEMITONES = (0, 2, 4, 5, 7, 9, 11)


@functools.lru_cache(maxsize=None)
def _key(step, alter, mode):
    """A key's accidentals as {step: alteration} (natural minor), and the key."""
    tonic = music21.pitch.Pitch(STEPS[step], accidental=alter)
    key = music21.key.Key(tonic.name, mode)
    return {STEPS.index(p.step): int(p.alter) for p in key.pitches[:7]}, key


def numeral_accidental(step, alter, scale):
    """Semitones between a root and the key's note of the same letter: the accidental in front of its numeral."""
    return alter - scale[step]


def _respellable(step, alter, scale):
    """Whether the root, named with another letter, has a smaller accidental in front of its numeral."""
    now = abs(numeral_accidental(step, alter, scale))
    pc = SEMITONES[step] + alter
    for other in range(7):
        a = (pc - SEMITONES[other] + 6) % 12 - 6  # the alteration that names the same pitch with that letter
        if abs(a) <= 2 and abs(numeral_accidental(other, a, scale)) < now:
            return True
    return False


def _components(timeline):
    c = timeline.get("components", {})
    return list(c.values()) if isinstance(c, dict) else c


def _harmony(name, timeline, report):
    comps = sorted(_components(timeline), key=lambda c: (c["time"], c.get("kind") != "MODE"))
    key = None
    for c in comps:
        if c.get("kind") == "MODE":
            scale, key = _key(c["step"], c["accidental"], "minor" if c["type"] == "minor" else "major")
            if abs(key.sharps) > 7:
                report("key-signature", name, c["time"], f"{key} has {abs(key.sharps)} accidentals")
            continue
        if c.get("kind") != "HARMONY" or key is None or c.get("display_mode") == "custom" or c.get("applied_to") \
                or c.get("quality") in SKIPPED_QUALITIES:
            continue
        accidental = numeral_accidental(c["step"], c["accidental"], scale)
        root = music21.pitch.Pitch(STEPS[c["step"]], accidental=c["accidental"]).name.replace("-", "b")
        if abs(accidental) >= 2:
            report("numeral-double-accidental", name, c["time"], f"{root} in {key}")
        elif _respellable(c["step"], c["accidental"], scale):
            report("root-fits-respelled", name, c["time"], f"{root} in {key}")


def _hierarchy(name, timeline, report):
    by_level = {}
    for c in _components(timeline):
        by_level.setdefault(c["level"], []).append(c)
    for level, comps in by_level.items():
        comps.sort(key=lambda c: (c["start"], c["end"]))
        for a, b in zip(comps, comps[1:]):
            if b["start"] < a["end"] - TOLERANCE:
                report("section-overlap", name, b["start"],
                       f"level {level}: {b.get('label', '')!r} starts at {b['start']:.3f}, "
                       f"before {a.get('label', '')!r} ends at {a['end']:.3f}")


def _pitch(name):
    return music21.pitch.Pitch(name[0] + name[1:].replace("b", "-"))


@functools.lru_cache(maxsize=None)
def bass_rule(symbol):
    """The rule a letter symbol's slash bass breaks, or None."""
    if symbol[:1] not in STEPS or "/" not in symbol:
        return None  # a Roman numeral (its / is an applied chord) or no bass
    head, bass = symbol.rsplit("/", 1)
    chord = music21.harmony.ChordSymbol(head[0] + head[1:].replace("b", "-", 1) if head[1:2] == "b" else head)
    bass = _pitch(bass)
    if bass.name in {p.name for p in chord.pitches}:
        return None
    if bass.pitchClass in {p.pitchClass for p in chord.pitches}:
        return "bass-enharmonic"
    return "bass-not-chord-tone"


def _bass(path, report):
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["harmony_or_key"] != "harmony" or r.get("display_mode") == "custom":
                continue
            rule = bass_rule(r["symbol"])
            if rule:
                report(rule, Path(path).name, float(r["time"]), r["symbol"])


def lint(tla_path, harmony_csvs=()) -> dict:
    """The rules' findings for one converted file: counts per level and rule, and the first few cases."""
    out = {"errors": 0, "warnings": 0, "rules": {}, "examples": []}

    def report(rule, where, time, what):
        level = LEVELS[rule]
        out[level + "s"] += 1
        out["rules"][rule] = out["rules"].get(rule, 0) + 1
        if len(out["examples"]) < EXAMPLES:
            out["examples"].append({"rule": rule, "level": level, "where": where, "time": round(time, 3), "what": what})

    data = json.loads(Path(tla_path).read_text(encoding="utf-8"))
    for timeline in data["timelines"].values():
        if timeline.get("kind") == "Harmony":
            _harmony(timeline.get("name", ""), timeline, report)
        elif timeline.get("kind") == "Hierarchy":
            _hierarchy(timeline.get("name", ""), timeline, report)
    for path in harmony_csvs:
        _bass(path, report)
    return out
