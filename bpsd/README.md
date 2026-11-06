# Beethoven Piano Sonata Dataset (BPSD) v2 to TiLiA

Makes one TiLiA file per movement and performance of the [Beethoven Piano Sonata Dataset v2](https://doi.org/10.5281/zenodo.12783403)
(Zeitler, Weiß, Arifi-Müller and Müller; CC BY 3.0): the first movements of the 32 piano sonatas in 11 performances, 352 files.
Each file has four timelines:

- **Measures** (beat): the bars of the performance, showing the number printed in the score (repeats show their numbers again; the pickup is 0);
- **Structure** (hierarchy): BPSD's coarse sections on level 2 and its fine sections on level 1;
- **Harmony** (harmony): the local keys and the chords, as symbols that TiLiA reads back as BPSD's chords (translated by [format-converters](https://github.com/TimeLineAnnotator/format-converters));
- **Chords (unparsed)** (marker): the chords TiLiA cannot hold, with the reason as comment.

The scores are not included, and neither is any audio: the four recordings that BPSD offers freely (AS35, FG58, FJ62, WK64) are loaded by the notebook from BPSD's
archive while the files are made, and left out of the package. [`NOTICE.md`](NOTICE.md) says which recordings exist and where, and that BPSD's annotations refer to its modified audio.

## Run

Install as in the [top-level README](../README.md), then from the repository root:

```
python bpsd/convert.py --out OUT [--only ID ...] [--package DIR] [--no-tilia] [--zip ARCHIVE [--audio]]
```

- `--only ID ...`: convert only these items; an ID is `<piece>_<performer>`, e.g. `Op002No1-01_AB96`. Performers: AB96 AS35 DB84 FG58 FG67 FJ62 JJ90 MB97 MC22 VA81 WK64.
- Without `--zip` the converter reads only the files it needs from BPSD's remote archive (HTTP range requests, md5 from `checksums.json`).
- `--zip ARCHIVE`: read from the downloaded archive instead; `--audio` also loads the four recordings that BPSD's archive offers (AS35, FG58, FJ62, WK64).
- `--package DIR`: also builds `DIR/bpsd-v2-tilia.zip` (the `.tla` files without media or file paths, `LICENSE`, `NOTICE.md`).
- `--no-tilia`: write the CSVs and scripts only.

It writes `OUT/csv/<ID>/*.csv`, `OUT/scripts/<ID>.txt`, `OUT/tla/<ID>.tla` and `OUT/summary.json`, which counts every layer in the saved file
against the rows of the source files. The command syntax lives in one function, `write_script`.

`convert.ipynb` does the full run (it downloads the whole 2.1 GB archive, checks its md5, converts all 352 items and builds the package);
set `DATASET_CONVERTERS_OUT` to the output folder and `TILIA` to TiLiA's command line. It needs TiLiA with `timelines add harmony` and `timelines import harmony`.

## How the bar numbers are found

BPSD numbers the bars of its unfolded scores. `bars.py` aligns each unfolded MusicXML score with the score with repetitions,
bar by bar on the notes, with the fewest jumps; the printed number of an unfolded bar is that of the bar it repeats.
(music21's `expandRepeats` does not give BPSD's unfolding for every piece.)

## Tests

`pytest bpsd/tests`: unit tests, the Op. 2 No. 1 fixtures (Brendel, a performance with a cut, and Schnabel) as CSVs and through TiLiA.

## Reference

Zeitler, J., Weiß, C., Arifi-Müller, V., & Müller, M. (2024). BPSD: A Coherent Multi-Version Dataset for Analyzing the First Movements of Beethoven's Piano Sonatas. Transactions of the International Society for Music Information Retrieval, 7(1), 195-212. https://doi.org/10.5334/tismir.196

BPSD's description (<https://zenodo.org/records/12783403>) says that four of the eleven performances are "in the public
domain and freely accessible for research purposes". Wilhelm Kempff's 1964 recording (WK64) may still be protected in
the EU until about 2035: since the 2011 term extension, a recording published from 1963 on is protected for 70
years. The package ships no audio.
