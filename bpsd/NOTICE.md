# Beethoven Piano Sonata Dataset v2 as TiLiA files

352 TiLiA files (`.tla`): the first movements of Beethoven's 32 piano sonatas, each in the 11 performances of the
Beethoven Piano Sonata Dataset (BPSD). A file is named `<piece>_<performer>.tla`, for example `Op002No1-01_AB96.tla`.

## Licence and attribution

The annotations come from the Beethoven Piano Sonata Dataset v2, released under the
[Creative Commons Attribution 3.0 Unported licence](https://creativecommons.org/licenses/by/3.0/) (CC BY 3.0); this
package is released under the same licence. The dataset is by Johannes Zeitler, Christof Weiß, Vlora Arifi-Müller
and Meinard Müller, and is at <https://doi.org/10.5281/zenodo.12783403> (Zenodo record 12783403).
Its authors ask to cite:

> Zeitler, J., Weiß, C., Arifi-Müller, V. and Müller, M. (2024) BPSD: A Coherent Multi-Version Dataset for Analyzing
> the First Movements of Beethoven's Piano Sonatas. *Transactions of the International Society for Music Information
> Retrieval*, 7(1), 195-212. <https://doi.org/10.5334/tismir.196>

The files were made with the converter in the `bpsd/` folder of <https://github.com/TimeLineAnnotator/dataset-converters>.

## What the files hold

Every file has four timelines, with the metadata title, composer, performer, corpus, licence and notes.

| Timeline | Kind | Contents |
| --- | --- | --- |
| Measures | beat | One beat per bar, from BPSD's `ann_audio_measure`: the time at which the bar starts, and a final beat for the end of the movement. |
| Structure | hierarchy | Level 2: BPSD's coarse sections (`ann_audio_structureCoarse`). Level 1: its fine sections (`ann_audio_structureFine`), labelled with the part after the colon, e.g. `FirstGroup`. |
| Harmony | harmony | The local keys (`ann_audio_localkey`) and the chords (`ann_audio_chord`). |
| Chords (unparsed) | marker | The chords that TiLiA's harmony timeline cannot hold; the label is BPSD's numeral, the comment says why. |

All times are the seconds of BPSD's audio. BPSD transferred its score annotations onto each performance; the files use
that transfer as it is and do not place anything again.

## What the conversion changed

- **Bar numbers.** BPSD numbers the bars of an unfolded score, in which every repeat is written out (the repeated
  exposition of Op. 2 No. 1 is bars 49 to 96). The Measures timeline shows the number printed in the score, so a
  repeated bar shows its number again. The pickup bar is 0, the last beat shows the number after the last bar. The
  printed numbers were found by aligning BPSD's unfolded MusicXML scores with its scores with repetitions bar by bar.
  Where a repeat sign cuts a printed bar in two, the two halves count as one bar. So do the two halves of a bar
  that a fermata and a double bar line cut in two (Op. 10 No. 2, bars 119/120 and 139/140; Op. 78, the Adagio's last
  bar, bars 4/5, so that the Allegro starts at 5), when BPSD's unfolded score has them as one bar.
  BPSD's scores number the two endings of a volta in sequence, while many editions number them otherwise, so a bar
  number can differ from such an edition by a few bars after a volta (the measure tables of DCML's Beethoven piano
  sonatas differ from these in the last bar number for 13 of the 28 movements they cover).
- **Keys and chords.** BPSD writes chords as Roman numerals in the BPS-FH notation (`roman`, relative to `localkey`)
  and as Harte labels. TiLiA reads its own symbols, so each chord is written as a symbol that TiLiA reads back as the
  same pitch classes and bass as BPSD's Harte label (`extended`): a Roman numeral where one exists, otherwise a letter
  symbol, with BPSD's numeral as custom text and a comment saying how the symbol differs. The translation is the one of
  [format-converters](https://github.com/TimeLineAnnotator/format-converters). Chords labelled `N` or `X` are not chords and
  are not placed. A key is written before the chords that start at the same time.
- **Structure.** Rows that BPSD repeats verbatim are written once. Fine labels without a colon (such as
  `Development`) are kept as they are.
- **No scores.** The scores of BPSD are not part of these files.
- **No audio.** The files carry no recording and no media path; the media length is the end of the annotations.

## Recordings

BPSD's annotations refer to its audio, which is in the `1_Audio` folder of the BPSD archive
(<https://zenodo.org/records/12783403>, `Beethoven_Piano_Sonata_Dataset_v2.zip`) and not in this package.
BPSD's description says that four of the eleven performances are "in the public domain and freely accessible for
research purposes". They are the first four below. The status of Wilhelm Kempff's 1964 recording (WK64) may
differ in the EU: since the 2011 term extension, a recording published from 1963 on is protected for 70 years, so
it may be protected until about 2035. Check the rights before reusing any recording.

| Code | Performer | Recorded | Label |
| --- | --- | --- | --- |
| AS35 | Artur Schnabel | 1935 | Warner Classics |
| FG58 | Friedrich Gulda | 1958 | Decca |
| FJ62 | Fritz Jank | 1962 | Instituto Piano Brasileiro |
| WK64 | Wilhelm Kempff | 1964 | Deutsche Grammophon |

The other seven performances are commercial recordings, which BPSD does not distribute. Its
`0_RawData/audio_ripped/audio_versions_metadata.csv` names them by EAN and MusicBrainz release id:

| Code | Performer | Recorded | Label | EAN | MusicBrainz release |
| --- | --- | --- | --- | --- | --- |
| FG67 | Friedrich Gulda | 1967 | Amadeo/Decca | 28947687610 | 83f869ea-fc64-4fe9-b424-52d4282f706f |
| VA81 | Vladimir Ashkenazy | 1981 | London Records | 28944370621 | 36fcb34f-59ab-3e4d-a066-3067ed82ed33 |
| DB84 | Daniel Barenboim | 1984 | Deutsche Grammophon | 028941375926, 028941376626 | 261a38ba-9c56-458e-9a4d-c7b6b4acb3a3, b4b49c3d-f86a-4701-b967-d4e726ab8ef0 |
| JJ90 | Jeno Jando | 1990 | NAXOS | 730099150224 | 2f94e0a3-be66-4894-9c9d-83d5890081da |
| AB96 | Alfred Brendel | 1996 | Philips | 28941257529 | 6f419224-c6fb-4c38-871e-5799b755a387 |
| MB97 | Malcolm Bilson et al. | 1997 | Claves | 7619931970721 | 718bac94-7c2c-48ea-8f30-dc230aab019d |
| MC22 | Muriel Chemin | 2022 | Odradek | 855317003615 | n.a. |

**The annotations refer to BPSD's modified audio.** BPSD edited some recordings ("structural modifications") so that
all versions of a piece follow the same structure. The 26 performances that were edited have a file in
`2_Annotations/ann_audio_modifications` of the archive: one row per modification, with its `start` and `end` in
seconds of the unedited recording (`Beethoven_Op002No1-01_AB96.csv`, for example, lists one cut). The script that applied them is `3_Scripts/01_audio_modifications.ipynb` of the archive. The recordings in the
archive's `1_Audio` folder are already edited. A commercial recording has to be edited the same way before the times
in these files fit it.

## Problems in the source data

- **Bars after the end.** In two WK64 files (Op. 26 and Op. 31 No. 2) the end row of `ann_audio_measure` lies
  before the start of the last bar (Op. 26: 480.004 s against an end of 477.971 s; Op. 31 No. 2: 498.454 s against
  496.010 s). The converter keeps the bar, so that the rows match the source, and puts it 1 ms before the end.
- **Bars of the printed score that the unfolded score lacks.** Where a movement has first and second endings, BPSD's
  unfolded score has only the ending that is played, so the printed numbers skip the other one (for example
  Op. 13: 131 to 134 in the XML numbers). Op. 10 No. 2 has a first ending at the end of the movement (bar 206)
  that the unfolded score lacks, and the last bar shows the number after it.
- **Op. 10 No. 2, bars 119/120 and 139/140.** The score with repetitions writes each pair as two bars (3/2 and 1/2
  quarter notes of a 2/4 bar), joined by a fermata and a double bar line; the unfolded score has one bar each. Every
  unfolded bar there is the two printed bars together, so the pair shows one number. In the second pass over the
  exposition's ending (unfolded bar 133) the unfolded bar has the notes of the first ending, so it shows that
  ending's number.
- **Edited bars.** Some unfolded bars differ a little from the printed ones (a pickup turned into rests, say). The
  alignment tolerates that; the printed numbers of the bars with the largest differences (Op. 10 No. 3, Op. 22 and
  Op. 109 have a bar with nothing in common) rest on their neighbours.
