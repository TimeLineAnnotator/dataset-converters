# Annotated Mozart Piano Sonatas, as TiLiA files

54 movements of Mozart's 18 piano sonatas, one `.tla` file each, converted from the DCML corpus
*The Annotated Mozart Sonatas: Score, Harmony, and Cadence* (DCMLab/mozart_piano_sonatas, v2.3,
https://github.com/DCMLab/mozart_piano_sonatas, DOI 10.5281/zenodo.7424962).

## Licence and attribution

The annotations are by the DCML (Digital and Cognitive Musicology Lab) and are licensed under
CC BY-NC-SA 4.0 (see `LICENSE`): attribution, non-commercial use, and sharing alike. These files are
adaptations of them and carry the same licence. Please cite the dataset's data report:

> Hentschel, J., Neuwirth, M. and Rohrmeier, M. (2021) The Annotated Mozart Sonatas: Score, harmony,
> and cadence. Transactions of the International Society for Music Information Retrieval, 4(1), 67-80.
> https://doi.org/10.5334/tismir.63

Each file's notes name the movement's annotators and reviewers (from the dataset's `metadata.tsv`).
The scores follow the Neue Mozart-Ausgabe, as the dataset states.

## What the conversion did

Every file has five timelines, all present even when empty:

- **Measures** (beat): one bar per row of DCML's measures table, numbered with DCML's printed bar
  number `mn` (a pickup is bar 0; numbers repeat over voltas). A bar has as many beats as its time
  signature's numerator (6/8 gives six eighth-note beats), evenly spaced over its nominal length; a
  partial bar keeps round(numerator x actual length / nominal length) of them, at least one.
- **Phrases** (hierarchy, one level): `{` opens a phrase, `}` closes it, `}{` closes one and opens the
  next. A `}` with nothing open closes a phrase that starts where the previous one ended (or at the
  start of the piece); a phrase still open at the end closes at the end of the piece; a `{` while one is
  open starts the phrase afresh there.
- **Harmony** (harmony): the local keys, made absolute (DCML writes them relative to the global key, as
  in `V/V`), and the chords. A chord is written as the Roman numeral, or the letter symbol, that TiLiA
  reads as exactly the chord DCML's tables hold (its chord tones, added tones and bass); where only an
  approximation was possible the label is shown as custom text and the comment says why.
- **Cadences** (marker): one marker per cadence label (PAC, IAC, HC, DC, EC, PC, with a subtype after a
  dot where there is one).
- **Chords (unparsed)** (marker): chords TiLiA's parser cannot express, with DCML's label and the reason.
  Rows without a chord (empty or `@none`) are not chords and are not placed.

## Time

There is no recording. The convention is **one second stands for one quarter note**; the metadata field
`time unit` says so. A bar starts at its `quarterbeats_all_endings` (or `quarterbeats` in the 45
movements without voltas), a label at its own row's `quarterbeats_all_endings`, so voltas count once each,
in order. The media length is the end of the last bar. Labels are placed by time, so the bar fractions of
the older converter (`mn_onset`, in whole notes) are not used.

## Recordings

None. The files carry no media and no file paths. To annotate a recording, load it in TiLiA and
retime the timelines to it.
