# dcml-mozart

Converts DCML's *Annotated Mozart Piano Sonatas* (v2.3, [DCMLab/mozart_piano_sonatas](https://github.com/DCMLab/mozart_piano_sonatas), CC BY-NC-SA 4.0) into TiLiA files: one `.tla` per movement, 54 in all. It replaces the older `main.py`, which wrote CSVs for TiLiA's former `timeline import csv` syntax.

```
python dcml-mozart/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia]
```

Run it with the repository root on `PYTHONPATH` (or after `pip install -e .`), `TILIA` pointing at TiLiA's command line, and `format-converters` installed (it is a dependency in `pyproject.toml`). The harmony timeline needs a TiLiA with `timelines add harmony` and `timelines import harmony`.

- `--only K279-1 K331-1` converts those movements (IDs are the piece names in `dcml_files.txt`); the default is all 54.
- `--package DIR` builds `DIR/dcml-mozart-v2.3-tilia.zip`: the `.tla` files with file and media paths emptied, `LICENSE` and `NOTICE.md`.
- `--no-tilia` writes only the CSVs and scripts.

Output under `DIR`: `csv/<ID>/*.csv`, `scripts/<ID>.txt` (the TiLiA script, made by `write_script`), `tla/<ID>.tla`, and `summary.json` with, per movement and layer, the components in the saved file and the rows counted from the source tables. `convert.ipynb` does the full run (it reads `DATASET_CONVERTERS_OUT`).

The files it downloads are pinned: `md5s.json` holds the md5 of each of the 109 tables (checked by `common.download.fetch`), `dcml_files.txt` lists the movements.

## What a file holds

Timelines `Measures` (beats; one bar per row of the measures table, numbered with DCML's `mn`), `Phrases` (hierarchy), `Harmony` (local keys made absolute, and chords as Roman numerals or letters via `format_converters`), `Cadences` and `Chords (unparsed)` (markers). There is no recording: one second stands for one quarter note, and every label is placed by time from the `quarterbeats_all_endings` (or `quarterbeats`) columns. Details, and what the conversion changed, are in [`NOTICE.md`](NOTICE.md), which goes into the package.

## Tests

```
pytest dcml-mozart/tests
```

`test_convert.py` checks the CSVs and scripts for four movements (K284-1, K331-1, K280-1, K333-1) without TiLiA; `test_tilia.py` runs them through TiLiA and compares the saved files' counts with the source rows.
