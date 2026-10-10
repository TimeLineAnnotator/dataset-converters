"""Spelling of SWD's performance labels, taken from the score's.

SWD's chords and keys for each performance (``ann_audio_*``) are the score's (``ann_score_*``), transposed to
the performance's key and named from a table of sharps: no flats, no E#, B#, Cb or Fb. As Roman numerals they
read #V for VI, or bbI for VII. The score's chords are spelled as the score spells them, so each performance
chord is respelled as its score chord transposed, and each key's tonic as those chords spell it.
"""
import collections
import re

import music21

LABEL = re.compile(r"([A-G][#b]*)(?::([^/]+))?(?:/([A-G][#b]*))?")
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def parse(label):
    """A Harte label as (root, quality, bass): 'Db:(3,#5,7)/C', and 'D#/G' for D#:maj/G. N, X and others are None."""
    m = LABEL.fullmatch(label.strip())
    return (m[1], m[2] or "maj", m[3]) if m else None


def pitch_class(name):
    return (STEPS[name[0]] + name.count("#") - name[1:].count("b")) % 12


def _shape(parts, shift=0):
    """What a chord sounds like: root and bass as pitch classes, moved by ``shift`` semitones."""
    if parts is None:
        return None
    root, quality, bass = parts
    return (pitch_class(root) + shift) % 12, quality, None if bass is None else (pitch_class(bass) + shift) % 12


def chord_shift(score, performance, item):
    """Semitones from the score's chords to the performance's: the one shift that makes the two lists equal."""
    shifts = [s for s in range(12)
              if len(score) == len(performance)
              and all(_shape(a, s) == _shape(b) for a, b in zip(score, performance))]
    if len(shifts) != 1:
        raise ValueError(f"{item}: the performance's chords are not the score's, transposed")
    return shifts[0]


def _name(pitch):
    return pitch.name.replace("-", "b")


def _names(chords):
    return [n for c in chords if c for n in (c[0], c[2]) if n]


def transposition(score, shift):
    """The interval of ``shift`` semitones that writes the score's notes with the fewest accidentals, and of
    two that write as many, the one that is neither augmented nor diminished.

    F minor down a whole step is E-flat minor (a major second), not D-sharp minor (a diminished third).
    """
    notes = [music21.pitch.Pitch(n.replace("b", "-")) for n in _names(score)]
    best = None
    for letter in "CDEFGAB":
        for alter in (0, -1, 1, -2, 2):
            target = music21.pitch.Pitch(letter, accidental=alter)
            if target.pitchClass != shift:
                continue
            interval = music21.interval.Interval(music21.pitch.Pitch("C"), target)
            cost = (sum(abs(interval.transposePitch(p).alter) for p in notes), interval.simpleName[0] in "Ad")
            if best is None or cost < best[0]:
                best = (cost, interval)
    return best[1]


def respell(parts, interval):
    """The score chord's label, transposed: 'Eb:7/G' a major second down is 'Db:7/F'."""
    root, quality, bass = parts
    move = lambda n: _name(interval.transposePitch(music21.pitch.Pitch(n.replace("b", "-"))))
    return f"{move(root)}:{quality}" + (f"/{move(bass)}" if bass else "")


def _tonic_quality(quality):
    if quality.startswith("min"):
        return "min"
    if quality in ("maj", "7", "maj7", "maj6"):
        return "maj"
    return None


def key_offset(keys, chords):
    """Semitones by which an annotator's keys sit below the chords: 0 unless the keys were transposed apart from them.

    keys: rows with start, end and key ('D:min'); chords: (time, parts). The offset is the one under which the most
    chords are the tonic triad of the key in force. In D911-06 and D911-22 two annotators' keys are 2 and 4
    semitones below the performance's chords; everywhere else this is 0.
    """
    spans = [(float(k["start"]), float(k["end"]), *k["key"].strip().split(":")) for k in keys]

    def tonic_chords(offset):
        hits = 0
        for time, parts in chords:
            if parts is None:
                continue
            for start, end, tonic, mode in spans:
                if start <= time < end:
                    hits += (pitch_class(parts[0]) - pitch_class(tonic) - offset) % 12 == 0 \
                        and _tonic_quality(parts[1]) == mode
                    break
        return hits

    return max(range(12), key=lambda o: (tonic_chords(o), o == 0))


def spellings(labels):
    """Pitch class -> its commonest name among the labels' roots and basses."""
    count = collections.defaultdict(collections.Counter)
    for name in _names(labels):
        count[pitch_class(name)][name] += 1
    return {pc: c.most_common(1)[0][0] for pc, c in count.items()}


def key_label(tonic_pc, mode, spelled):
    """A key, its tonic named as the chords name that pitch class; otherwise, or past seven sharps or flats,
    the name with the smaller key signature."""
    def signature(name):
        return abs(music21.key.Key(name.replace("b", "-") if mode == "maj" else name.replace("b", "-").lower()).sharps)

    sharp = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][tonic_pc]
    flat = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"][tonic_pc]
    name = spelled.get(tonic_pc)
    if name is None or signature(name) > 7:
        name = min((flat, sharp), key=signature)
    return f"{name}:{mode}"


def enharmonic_shift(key, spelled):
    """The interval from the chords' name of a key's tonic to the key's own, when they differ: G-flat minor (nine
    flats) is written F-sharp minor, and the chords in it move with it (a diminished second). None otherwise."""
    name = key.split(":")[0]
    theirs = spelled.get(pitch_class(name))
    if theirs is None or theirs == name:
        return None
    return music21.interval.Interval(music21.pitch.Pitch(theirs.replace("b", "-") + "4"),
                                     music21.pitch.Pitch(name.replace("b", "-") + "4"))
