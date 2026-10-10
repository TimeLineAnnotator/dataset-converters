# Schubert Winterreise Dataset (SWD) v2.1

Converts the annotations of the [Schubert Winterreise Dataset](https://doi.org/10.5281/zenodo.10839767) (CC BY 3.0)
into TiLiA files: one per song and performance, 24 songs × 9 performances = 216. The performers are AL98, FI55, FI66,
FI80, HU33, OL06, QU98, SC06 and TR99; a file is called `Schubert_D911-<song>_<performer>.tla`.

Each file has these timelines:

- **Measures**: a beat timeline of the performance's bars, numbered as printed in the IMSLP edition (repeats and pickups
  included; see [`NOTICE.md`](NOTICE.md)).
- **Structure**: the structural parts, one level.
- **Harmony**: annotator 1's local keys (the global key where that annotator gives none) and the chords, shown as
  Roman numerals.
- **Local keys (ann1)**, **(ann2)**, **(ann3)**: each annotator's local keys, on a timeline of its own.
- **Chords (unparsed)**: chords that TiLiA's harmony timeline cannot hold, as markers with the reason.

Chords and keys are spelled from SWD's score annotations: the performance annotations name every note with sharps,
and their chords are the score's, transposed (`spelling.py`; see [`NOTICE.md`](NOTICE.md)). Harte labels are
translated by [format-converters](https://github.com/TimeLineAnnotator/format-converters). Labels that
TiLiA can only approximate keep the source label as custom text, with a comment. None is dropped silently. The
`N` and `X` labels are not chords and are not placed.

## Run

Install as described in the top-level README, run from the repository root with `PYTHONPATH=.` (the `swd` folder is not an installed package), and set `TILIA` to the `tilia` executable and `QT_QPA_PLATFORM=offscreen` if there is no display. TiLiA needs the
harmony commands (`timelines add harmony`, `timelines import harmony by-time`) and a CSV import that applies the optional
harmony columns.

```
python swd/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia] [--audio]
```

- `DIR/csv/<ID>/*.csv` and `DIR/scripts/<ID>.txt` are written for each item, the script is run through TiLiA
  (`common.runner.run_script`) and saved as `DIR/tla/<ID>.tla`; `DIR/summary.json` holds, for each layer of each item, the
  number of components in the saved file and the number of source rows, and, under `keys_moved_to_the_chords`, the
  local-key timelines moved to agree with the chords (in semitones), and under `lint` the checks of `common.lint`.
- `--only` converts the given items, such as `Schubert_D911-01_HU33`. Without the whole archive in the cache, only the
  files an item needs are downloaded (HTTP range requests, checked against `members.json`).
- `--package DIR` builds `DIR/swd-v2.1-tilia.zip` from the `.tla` files without media or file paths, with `LICENSE` and
  `NOTICE.md`.
- `--no-tilia` writes the CSVs and scripts only.
- `--audio` loads the recordings of HU33 and SC06 from the whole archive (downloaded, 0.7 GB, then extracted into the
  cache). The package never holds audio, and the packaged files have no media path.

`convert.ipynb` does the full run: it reads the output folder from `DATASET_CONVERTERS_OUT`, downloads and checks the
archive (md5 591c377c6d3db522fd159b8b70180978), converts all 216 items with the recordings, builds the package into
`<out>/package` and prints the totals. `write_script` in `convert.py` is the one function that makes the script text.

`download.py` continues an interrupted download of the archive; Zenodo stalls long transfers.

## Tests

```
pytest swd/tests
```

The tests read the files of two songs of HU33 (song 1, whose repeat is unfolded in the score, and song 2, which has a
pickup) from the archive, and run them through TiLiA. `test_spelling.py` checks the spelling on songs 3 (OL06, in
E-flat minor, and HU33), 6 (HU33) and 22 (SC06), whose annotators' keys are moved. Between them they cover the measure grid with printed numbers, the structure level,
the Harte chords and keys as format-converters reports them, key rows before chord rows, and the counts in the saved files
against the source rows.
