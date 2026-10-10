# Choro Songbook Corpus v1.3.3

Converts the [Choro Songbook Corpus](https://doi.org/10.5281/zenodo.21219604) (DCMLab/choro, CC BY-NC-SA 4.0) into
TiLiA files: one per piece, 295, called `<songbook>_<name>_WF.tla` after the corpus's transcriptions
(`1_alvorada_WF.tla`). There is no recording: one second stands for one quarter note.

Each file has these timelines:

- **Measures**: a beat timeline of the bars, numbered in playing order as the corpus's table numbers them.
- **Form**: the parts (Intro, A, B, C, Coda, ...) on level 2, above the phrases (P0, P1, ...) on level 1.
- **Harmony**: the local keys, then the chords.
- **Chords (unparsed)**: chords that TiLiA's harmony timeline cannot hold, as markers with the reason (none in v1.3.3).

The corpus's Harte labels are translated by [format-converters](https://github.com/TimeLineAnnotator/format-converters).
Only a symbol on the transcribed chord's root is kept. A chord without an exact symbol is stored reduced (without its
added tones, then without its bass), with the transcribed label as custom text and a comment. None is dropped
silently. `NC` is not a chord and is not placed. [`NOTICE.md`](NOTICE.md) gives the details and the two corrections
made to the corpus's table.

## Run

Install as described in the top-level README, and set `TILIA` to the `tilia` executable and
`QT_QPA_PLATFORM=offscreen` if there is no display. TiLiA needs the harmony commands (`timelines add harmony`,
`timelines import harmony by-time`) and, for the labels shown as custom text, a CSV import that applies the optional
harmony columns (TimeLineAnnotator/desktop#631).

```
python choro/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia] [--jobs N]
```

- The corpus's zip (0.5 MB) is downloaded into the cache and checked (md5 0f8a0dadb52577fd3c51ef82daf31bdb).
- `DIR/csv/<ID>/*.csv` and `DIR/scripts/<ID>.txt` are written for each piece, the script is run through TiLiA
  (`common.runner.run_script`) and saved as `DIR/tla/<ID>.tla`. `DIR/summary.json` holds, for each layer of each
  piece, the number of components in the saved file and the number of source rows. `DIR/source-report.json` lists,
  per piece, the bars whose chords don't add up to the time signature and the corrections made to the table.
- `--only` converts the given pieces, such as `1_alvorada_WF`.
- `--package DIR` builds `DIR/choro-v1.3.3-tilia.zip` from the `.tla` files without file paths, with `LICENSE` and
  `NOTICE.md`.
- `--no-tilia` writes the CSVs and scripts only.

`convert.ipynb` does the full run into `DATASET_CONVERTERS_OUT`. `write_script` in `convert.py` is the one function
that makes the script text.

## Tests

```
pytest choro/tests
```

The tests read three pieces: *Alvorada* (an Intro, and a phrase played twice in a row), *Rosa* (bars that don't add up
to 3/4, and triads over their minor seventh) and *Enigmático* (a slash chord whose Harte label has another bass). They
check the bar grid, the durations, keys before chords, the parts and phrases, the chord translations, and, through
TiLiA, the counts in the saved files against the source rows.
