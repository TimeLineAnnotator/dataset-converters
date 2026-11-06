# Choro Songbook Corpus, as TiLiA files

295 choros, waltzes, polkas and other pieces, one `.tla` file each, converted from the
*Choro Songbook Corpus* (DCMLab/choro, v1.3.3, https://github.com/DCMLab/choro,
DOI 10.5281/zenodo.21219604): the chord symbols and the form of every piece in the three volumes of the
*Choro Songbook* (Chediak, Sève, Souza and Dininho, eds., Lumiar Editora, 2009 and 2011), as the corpus's
authors transcribed them.

## Licence and attribution

The corpus is licensed under CC BY-NC-SA 4.0 (see `LICENSE`): attribution, non-commercial use, and sharing
alike. These files are adaptations of it and carry the same licence. Please cite:

> Moss, F. C., Fernandes de Souza, W. and Rohrmeier, M. (2020) Harmony and form in Brazilian Choro: A
> corpus-driven approach to musical style analysis. Journal of New Music Research, 49(5), 416-437.
> https://doi.org/10.1080/09298215.2020.1797109

## What the conversion did

The converter reads the corpus's table (`data/choro.tsv`), which lists every chord in the order the piece is
played, repeats written out, and each piece's transcription (`data/transcriptions/*.txt`) for its form rules.
Every file has four timelines, all present even when empty:

- **Measures** (beat): one bar per bar number of the table, which numbers bars in playing order from 1 (so
  not as printed in the songbook). A bar has as many beats as its time signature's numerator, evenly spaced
  over its nominal length. A bar whose chords add up to another length (a slip in 16 pieces, listed in the
  converter's `source-report.json`) keeps round(numerator x actual length / nominal length) beats, at least
  one, and the chords keep their written durations.
- **Form** (hierarchy, two levels): the parts (Intro, A, B, C, Coda, ...) above the phrases (P0, P1, ...).
  The transcriptions often write a return to a part (the A after B) as its phrases, outside any part
  (`S: $PartA $PartB $P1 $P2`), and the table gives those rows no part. Such a run of phrases is labelled
  with the part (A, B, C, ...) whose rule has them, and its comment says so (385 parts). A phrase in
  several parts' rules takes its neighbour's part. Phrases in no part's rule (transitions, and vamps that
  only the intro or the fadeout plays) have no part above them (423 phrases). A phrase that the rules play
  twice in a row is split into two units of equal length.
- **Harmony** (harmony): the local keys and the chords, from the table's Harte labels. A chord is written
  as the letter symbol that TiLiA reads as exactly its notes, on its root and over its bass. Otherwise the
  transcribed label is shown as custom text and the stored chord is, in this order:
  - the same notes under another chord's name, when the bass is not in the chord and the symbol takes it
    in (`D/C` is stored as D7/C);
  - the chord without its added tones in brackets (`G7(13)` as G7, `D7(b9)` as D7);
  - the chord without its bass, or without both;
  - the shared translator's own approximation on the same root.

  Each such chord's comment says which. A symbol on another root than the transcription's is never used,
  although TiLiA can read some chords' notes that way (D7(b9) as a diminished ninth on C).
- **Chords (unparsed)** (marker): chords none of the above can store. In v1.3.3 there are none. `NC` (no
  chord) is not a chord and is not placed.

Two corrections to the table, both listed per piece in `source-report.json`:

- Where a slash chord's Harte label has another bass than the transcribed label (`Eb7/Bb` as `Eb:7/b5`,
  124 chords in 32 pieces), the transcribed bass is used, spelled as written (`Eb:7/5`).
- `7M` among the added tones (`F:min(7M,9)`) is read as Harte's `7`.

Two transcriptions have no rows in the table (`2_chorinho_pra_voce_WF`, `3_um_chorinho_na_aldeia_WF`) and
are not converted.

## Time

There is no recording. The convention is **one second stands for one quarter note**; the metadata field
`time unit` says so. The table's `duration` column is in whole notes (0.5 is a 2/4 bar). A chord's time is
the sum of the durations before it, and the media length is the end of the last chord.

## Recordings

None. The files carry no media and no file paths. To annotate a recording, load it in TiLiA and retime
the timelines to it.
