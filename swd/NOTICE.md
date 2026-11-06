# Schubert Winterreise Dataset (SWD) v2.1 as TiLiA files

This package holds 216 TiLiA files (`.tla`): the 24 songs of Schubert's *Winterreise*, D 911, in each of nine
performances. They are converted from the annotations of the Schubert Winterreise Dataset, version 2.1.

## Source and attribution

Christof Weiß, Frank Zalkow, Vlora Arifi-Müller, Meinard Müller, Hendrik Vincent Koops, Anja Volk and
Harald G. Grohganz: *Schubert Winterreise Dataset (SWD)*, version 2.1.
doi:[10.5281/zenodo.10839767](https://doi.org/10.5281/zenodo.10839767).
The dataset is described in: C. Weiß et al., "Schubert Winterreise dataset: A multimodal scenario for music
analysis", ACM Journal on Computing and Cultural Heritage (JOCCH), 2021, doi:10.1145/3429743.

Licence of the annotations, and so of these files: Creative Commons Attribution 3.0 Unported (CC BY 3.0),
<https://creativecommons.org/licenses/by/3.0/>. The files are changed from the dataset's CSV annotations, as
described below. The converter is at <https://github.com/TimeLineAnnotator/dataset-converters> (folder `swd/`).

## What a file holds

Each file is named `Schubert_D911-<song>_<performer>.tla`, such as `Schubert_D911-01_HU33.tla`, and has these
timelines. Times are in seconds of the performance.

| Timeline | Content | Source |
| --- | --- | --- |
| Measures | one beat per bar, with the bar's printed number | `ann_audio_measure`, `ann_score-IMSLP_measure` |
| Structure | the structural parts (A1, B1, I1, ...), one level | `ann_audio_structure` |
| Harmony | annotator 1's local keys and the chords, shown as Roman numerals | `ann_audio_localkey-ann1`, `ann_audio_globalkey.csv`, `ann_audio_chord`, spelled from `ann_score_chord` |
| Local keys (ann1), (ann2), (ann3) | each annotator's local keys, on a timeline of its own | `ann_audio_localkey-ann1`, `-ann2`, `-ann3`, spelled like the chords |
| Chords (unparsed) | chords that TiLiA's harmony timeline cannot hold, as markers | `ann_audio_chord` |

The performances are transposed (HU33 sings "Gute Nacht" in C minor; the score is in D minor). The labels come
from each performance's own annotation files and are in the key that is sung.

## What the conversion changed

- **Bar numbers.** The audio annotation numbers bars through the unfolded score, 1 to n. The files show the bar
  numbers printed in the IMSLP (Peters) edition instead: row k of `ann_audio_measure` takes the number of row k of
  `ann_score-IMSLP_measure/Schubert_D911-<song>.csv`. In song 1, whose repeat is unfolded, the numbers go back
  from 38 to 7 where the repeat is played. A pickup (0.750, 0.833 or 0.917 in the audio file) is bar 0 of that
  list in songs 2, 3, 11, 14, 16, 19 and 20. The Peters edition counts the pickup of song 23 as bar 1, so that song's
  numbers begin at 1 on the pickup. The last row of the audio file marks the end of the last bar, not a bar; it gets the
  number after the last printed one.
- **Spelling.** SWD's annotations of the performances name every note with sharps (`D#:min` for E-flat minor,
  `A#` for B-flat), so their Roman numerals would read ♯V for VI. Its annotations of the score are spelled as the
  score spells them, and the performance's chords are the score's, transposed. Each chord is therefore written as
  its score chord, transposed to the performance by the interval that needs the fewest accidentals (F minor a step
  down is E-flat minor), and each key's tonic as those chords name it. A key that would need more than seven sharps
  or flats is written enharmonically (G-flat minor as F-sharp minor), with the chords in it.
- **Keys.** The Harmony timeline holds annotator 1's local keys, so that the Roman numerals read against them;
  where annotator 1 gives no key (in songs 7 and 8), the global key stands. In songs 6 and 22, annotators 2 and 3's
  keys for the performances lie a whole step and a major third below the performance's chords (for HU33's song 6,
  in D minor, they give C minor and A-sharp minor); they are moved up to the chords. A file's entry in
  `summary.json` names the moved timelines.
- **Chords.** Harte labels (`C:min7/G`, `Eb:maj`) are written as the text that TiLiA's harmony timeline
  stores exactly, by [format-converters](https://github.com/TimeLineAnnotator/format-converters), and are shown as
  Roman numerals. A chord that TiLiA can only approximate (for
  example an added ninth, or a bass outside the chord) is shown with its source label as custom text, and the
  comment says what TiLiA stores. A chord that TiLiA cannot hold at all is not dropped: it is a marker on
  "Chords (unparsed)" with the source label and the reason. The labels N and X (no chord) are not placed.
- Only the annotations are converted: no score, no lyrics, no note annotations.

## Recordings

No audio is in this package. The files do not refer to a recording.

- **HU33** (Gerhard Hüsch's 1933 performance, in SWD's README "the Huesch performance"): the licence file
  `03_ExtraMaterial/license_HU33.txt` of SWD points to the Public Domain Mark 1.0,
  <https://creativecommons.org/publicdomain/mark/1.0/>. SWD's recording of song 1 has an artificial repeat added,
  so that it matches the unfolded score.
- **SC06** (Randall Scarlata, baritone, and Jeremy Denk, piano, 2006; Isabella Stewart Gardner Museum, Boston):
  SWD's README says the performance is "published under the same license" as the dataset, CC BY 3.0, and that its
  audio files "must not be re-distributed in modified form". The licence file `03_ExtraMaterial/license_SC06.txt`
  says <https://creativecommons.org/licenses/by-nc-nd/3.0/>, which is CC BY-NC-ND 3.0. The two disagree.
  Take the stricter one for the recording unless the museum says otherwise.
- **AL98, FI55, FI66, FI80, OL06, QU98 and TR99** are commercial recordings. SWD does not include them and
  neither does this package; their annotations are in the files. To follow along, use your own copy of the
  recording that SWD's paper names for the performer code.

The files made by the converter's `--audio` option load the recordings of HU33 and SC06 from the SWD archive;
those files are not part of this package.
