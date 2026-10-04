"""Printed bar numbers of BPSD's unfolded bars.

BPSD numbers the bars of its unfolded scores (every repeat written out, bars 0..N with 0 the pickup). The
scores with repetitions show the printed numbers. Both are MusicXML, and every bar of the unfolded score
is a bar of the printed one, so the unfolding is recovered by aligning the two bar by bar on their notes:
the cheapest path through the printed bars that reproduces every unfolded bar, where the cost is the
number of jumps (a repeat) it takes. A printed bar that a repeat sign splits in two (the end of the
exposition and the pickup that follows it) is one bar of the unfolded score.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

JUMP = 5
OFF_SIGNS = 1  # added to a jump that is not from a closing repeat sign to the start of its section
INF = 10**9


@dataclass(frozen=True)
class Bar:
    number: str  # the number attribute of the printed bar
    notes: tuple  # sorted (onset, duration, voice, staff, pitch) of everything in it
    length: Fraction  # quarter notes of music in the bar
    nominal: Fraction  # quarter notes of a full bar of the time signature
    repeat_end: bool = False  # a repeat sign closes the bar
    repeat_start: bool = False  # a repeat sign opens the bar
    double_bar: bool = False  # a double bar line closes the bar


def read_bars(path) -> list[Bar]:
    part = ET.parse(path).getroot().find("part")
    bars, divisions, nominal = [], Fraction(1), Fraction(4)
    for m in part.findall("measure"):
        items, pos, end, repeat_end, repeat_start, double = [], Fraction(0), Fraction(0), False, False, False
        for el in m:
            if el.tag == "barline":
                repeat_end |= any(r.get("direction") == "backward" for r in el.findall("repeat"))
                repeat_start |= any(r.get("direction") == "forward" for r in el.findall("repeat"))
                double |= el.get("location", "right") == "right" and el.findtext("bar-style") == "light-light"
            elif el.tag == "attributes":
                if el.findtext("divisions"):
                    divisions = Fraction(int(el.findtext("divisions")))
                time = el.find("time")
                if time is not None and time.findtext("beats") and "+" not in time.findtext("beats"):
                    nominal = Fraction(int(time.findtext("beats")) * 4, int(time.findtext("beat-type")))
            elif el.tag == "note":
                duration = Fraction(int(el.findtext("duration") or 0)) / divisions
                chord = el.find("chord") is not None
                if chord:
                    pos -= last
                pitch = el.find("pitch")
                if pitch is not None:
                    name = (pitch.findtext("step"), pitch.findtext("alter") or "0", pitch.findtext("octave"))
                else:
                    name = ("rest",)
                items.append((pos, duration, el.findtext("voice") or "", el.findtext("staff") or "", name))
                pos += duration
                last = duration
                end = max(end, pos)
            elif el.tag == "backup":
                pos -= Fraction(int(el.findtext("duration"))) / divisions
            elif el.tag == "forward":
                pos += Fraction(int(el.findtext("duration"))) / divisions
                end = max(end, pos)
        bars.append(Bar(m.get("number"), tuple(sorted(items)), end, nominal, repeat_end, repeat_start, double))
    return bars


def _pitched(notes: tuple, shift: Fraction = Fraction(0)) -> frozenset:
    return frozenset((o + shift, *name) for o, _d, _v, _s, name in notes if name != ("rest",))


def _full_length(bars: list[Bar]) -> Fraction:
    """The length of a whole bar of the piece: the most common one."""
    return Counter(b.length for b in bars if b.length).most_common(1)[0][0]


def _is_split(printed: list[Bar], a: int, b: int, full: Fraction) -> bool:
    """Bars a and b are the two halves of one bar, which a repeat sign cuts apart."""
    if printed[a].length + printed[b].length != full:
        return False
    return printed[a].repeat_end or (b == a + 1 and printed[b].repeat_start)


def _is_halves(printed: list[Bar], a: int, b: int, full: Fraction) -> bool:
    """Bars a and b may be the two halves of one bar: a repeat sign cuts them apart (``_is_split``), or a double
    bar line does, as at a fermata. The second kind is only a candidate: the unfolded score decides. The halves
    add up to the usual bar of the piece or to a full bar of their own time signature (``nominal``), which may
    differ (Op. 78's Adagio is in 2/4 in a movement of 4/4)."""
    return _is_split(printed, a, b, full) or (
        b == a + 1 and printed[a].double_bar and printed[a].length + printed[b].length in (full, printed[a].nominal))


def _distance(a: frozenset, b: frozenset) -> float:
    """0 for the same notes (onset and pitch), 1 for none in common."""
    if not a and not b:
        return 0.0
    return len(a ^ b) / (len(a) + len(b))


def repeat_target(printed: list[Bar], end: int) -> int | None:
    """Where a backward jump from printed bar ``end`` lands by the repeat signs: None when no sign closes the
    bar, else the bar opened by the matching forward sign (the nearest one before it with no other backward
    sign between), or the first bar when there is none."""
    if not printed[end].repeat_end:
        return None
    for j in range(end, -1, -1):
        if printed[j].repeat_start:
            return j
        if j < end and printed[j].repeat_end:
            break
    return 0


def align(printed: list[Bar], unfolded: list[Bar]) -> tuple[list[tuple[int, int]], list[float]]:
    """For every unfolded bar, the printed bars it is made of, as (first, last) indices into ``printed``,
    and how far its notes are from them (0 = the same notes).

    BPSD edited some unfolded bars (a pickup turned into rests, say), so the match is not exact: the path
    minimises the sum of the distances plus ``JUMP`` for every jump (a repeat). Among paths with the same
    jumps, ``OFF_SIGNS`` prefers those whose jumps follow the repeat signs (see ``repeat_target``).
    """
    notes = [_pitched(b.notes) for b in printed]
    full = _full_length(printed)
    shorts = [j for j, b in enumerate(printed) if 0 < b.length < full]
    starts = [0] + [j for j, b in enumerate(printed) if b.repeat_start]
    pairs = {}
    for a in shorts:
        for b in {a + 1, *starts} if printed[a].repeat_end else {a + 1}:
            if b in shorts and a != b and _is_halves(printed, a, b, full):
                pairs[(a, b)] = _pitched(printed[a].notes) | _pitched(printed[b].notes, printed[a].length)
    candidates = [(j, j) for j in range(len(printed))] + list(pairs)
    sets = {u: (notes[u[0]] if u[0] == u[1] else pairs[u]) for u in candidates}

    closing = {}  # printed bar a jump may start from -> where the signs send it
    for p in candidates:
        target = repeat_target(printed, p[1])
        if target is not None:
            closing.setdefault(target, []).append(p)
    on_signs = {u: closing.get(u[0], []) for u in candidates}

    best: list[dict[tuple[int, int], tuple[float, tuple[int, int] | None]]] = []
    for i, bar in enumerate(unfolded):
        target = _pitched(bar.notes)
        layer = {}
        if i:
            floor = min(c for c, _ in best[i - 1].values())
            cheapest = min(best[i - 1], key=lambda u: best[i - 1][u][0])
        for u in candidates:
            d = _distance(sets[u], target) * 10
            if not i:
                layer[u] = (d if u[0] == 0 else INF, None)  # the unfolded score starts where the printed one does
                continue
            follow = (u[0] - 1, u[0] - 1) if u[0] and (u[0] - 1, u[0] - 1) in best[i - 1] else None
            options = [(floor + JUMP + OFF_SIGNS, cheapest)]
            options += [(best[i - 1][p][0] + JUMP, p) for p in on_signs[u] if p[1] + 1 != u[0]]
            for prev in {follow} | {(a, u[0] - 1) for a in shorts if (a, u[0] - 1) in best[i - 1]}:
                if prev is not None and prev[1] + 1 == u[0]:
                    options.append((best[i - 1][prev][0], prev))
            cost, prev = min(options, key=lambda o: (o[0], o[1]))
            layer[u] = (cost + d, prev)
        best.append(layer)
    last = len(printed) - 1  # ... and ends where it ends
    unit = min(best[-1], key=lambda u: (best[-1][u][0] + (0 if u[1] == last else INF), u))
    path, distances = [], []
    for i in range(len(unfolded) - 1, -1, -1):
        path.append(unit)
        distances.append(_distance(sets[unit], _pitched(unfolded[i].notes)))
        unit = best[i][unit][1]
    return path[::-1], distances[::-1]


def printed_numbers(repetitions, unfolded, pickup: bool) -> tuple[list[int], list[float]]:
    """The printed number of each bar of the unfolded score, in order, and how far each unfolded bar is from
    the printed bars it was matched to (0 = the same notes).

    ``pickup`` says whether the first bar is a pickup. It is not guessed from the bar lengths: a first bar
    shorter than the usual one is often no pickup (a slow introduction in another metre, say), so the caller
    takes it from BPSD's own numbering.

    The numbers are the MusicXML numbers of the printed score, moved so that the pickup is bar 0 and the first
    full bar is 1. Where the printed score splits one bar in two bars (a repeat sign in the middle of it), the
    second half has the first half's number and the bars after it count one less. So does a bar that a double bar
    line cuts in two (Op. 10/2 at a fermata), when the unfolded score has it as one bar.
    """
    printed, flat = read_bars(Path(repetitions)), read_bars(Path(unfolded))
    full = _full_length(printed)
    short = [0 < b.length < full for b in printed]
    path, distances = align(printed, flat)
    merged = {u for u in path if u[1] == u[0] + 1 and not _is_split(printed, *u, full)}  # cut by a double bar
    first_full = 1 if pickup else 0
    base = int(printed[first_full].number) - 1
    split = 0
    numbers = []
    for j, bar in enumerate(printed):
        if j > first_full and short[j - 1] and short[j] and (_is_split(printed, j - 1, j, full) or (j - 1, j) in merged):
            split += 1
        numbers.append(0 if pickup and j == 0 else int(bar.number) - base - split)
    return [numbers[a] for a, _ in path], distances
