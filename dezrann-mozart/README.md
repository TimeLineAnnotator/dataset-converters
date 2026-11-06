# dezrann-mozart

Adds the sonata-form structure and the texture of Dezrann's *Mozart piano sonatas* (v1.0, [doi:10.57745/OHRWPC](https://doi.org/10.57745/OHRWPC), annotations under the ODbL) to the TiLiA files that `dcml-mozart/convert.py` makes, for the nine movements that have them: K279-1 to K283-3 (every movement of K. 279, 280 and 283).

```
python dezrann-mozart/convert.py --dcml DIR --out DIR [--only ID ...] [--no-tilia]
```

`--dcml` is the output directory of `dcml-mozart/convert.py` (its `tla/<ID>.tla` files are read, never changed). Needs `TILIA` and `format-converters` (with its `.dez` reader). `convert.ipynb` does the full run (it reads `DATASET_CONVERTERS_OUT`, and `DATASET_CONVERTERS_DCML` for DCML's files, by default `<out>/../dcml`).

## What it does

- Downloads `mozart-piano-sonatas.zip` (md5-checked by `common.download.fetch`) and reads `analysis/<piece>_texture.dez` with `measure-map/<piece>.mm.json`.
- Keeps the labels of type `Structure` (a hierarchy of two levels: sections, level 2, over subjects and transitions, level 1) and `Texture` (one level). Left out: `Harmony`, `Cadence`, `Local Key` and `Phrase` (the DCML's own labels, already in its files), `Positive Feedback` and the two `Comment` labels (K283-2).
- Checks that the measure map's bar numbers and bar start times agree with DCML's Measures timeline, per movement.
- Writes the layers as CSVs by bar (`csv-by-bar/<ID>-structure.csv`, `-texture.csv`, TiLiA's hierarchy columns) and by time in seconds (`csv-by-time/`).
- Merges: TiLiA opens a copy of the DCML file, adds the hierarchies `Structure (Dezrann)` and `Texture (Dezrann)`, imports the by-time CSVs and saves `tla/<ID>.tla`. One function, `write_script`, writes that script, so only it changes when TiLiA has a non-interactive `tilia run`.
- Builds `package/dezrann-mozart-tilia-layers.zip`: the 18 by-bar CSVs, an ODbL `LICENSE` and `NOTICE.md`.

Time follows DCML's convention: one second stands for one quarter note, so Dezrann's position of q quarter notes is at q seconds (Dezrann's measure maps run through the score as written, each volta once, as DCML's quarterbeats do). Labels are imported by time, because a bar number that occurs twice (voltas) would get a label twice by measure.

The merged files are built locally and never shipped: they hold DCML's CC BY-NC-SA 4.0 timelines next to Dezrann's ODbL ones, and the two share-alike terms cannot both be met. See [`NOTICE.md`](NOTICE.md).

## Tests

```
pytest dezrann-mozart/tests
```

`test_layers.py` (no TiLiA): K279-1's nine structure labels and 100 texture labels, counts for all nine movements, the script and the package. `test_tilia.py`: the merged files, with DCML's timelines unchanged and one component per label. DCML's files are converted into a temporary directory unless `DEZRANN_TEST_DCML` names one that has them.
