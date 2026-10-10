# dataset-converters

Scripts that turn published music-analysis datasets into [TiLiA](https://github.com/TimeLineAnnotator/desktop) files. Each dataset has a folder of its own.

| Folder | Dataset | Formerly |
| --- | --- | --- |
| `bpsd/` | Beethoven Piano Sonata Dataset v2 (32 first movements, 11 performances each) | `TimeLineAnnotator/bpsd-to-tilia` |
| `dcml-mozart/` | DCML's Annotated Mozart Piano Sonatas (v2.3, 54 movements) | `TimeLineAnnotator/dcml-to-tilia` |
| `dezrann-mozart/` | Dezrann's structure and texture of Mozart's sonatas K. 279, 280 and 283 (v1.0), added to the DCML files | |
| `swd/` | Schubert Winterreise Dataset v2.1 | |

The datasets themselves are not stored here: the converters download them, and the TiLiA files they produce are build outputs.

The code is under the MIT licence. The datasets keep their own licences.

## Install

The converters need Python 3.12 or newer. TiLiA itself needs Python 3.12 or older, so use 3.12 for everything. Install this repository and TiLiA 0.7.0:

```
pip install -e .
pip install "TiLiA @ git+https://github.com/TimeLineAnnotator/desktop@eb605f720847cf86f47834e71bc5bd9f8e0cd606"
```

That commit is the `v0.7.0` tag. Do not write `@v0.7.0`: a branch of the same name shadows the tag, and pip would install 0.6.2.

## Run a converter

- `python bpsd/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia] [--zip ZIP [--audio]]`: one TiLiA file per movement and performance (352), with the bar numbers of BPSD's printed scores and a zip package; see [`bpsd/README.md`](bpsd/README.md).
- `python dcml-mozart/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia]`: one `.tla` per movement of the DCML Mozart sonatas, on a quarter-second time convention (there is no recording); see [`dcml-mozart/README.md`](dcml-mozart/README.md).

- `python dezrann-mozart/convert.py --dcml DIR --out DIR [--only ID ...] [--no-tilia]`: adds Dezrann's sonata-form structure and texture to the converted DCML files of nine movements; see [`dezrann-mozart/README.md`](dezrann-mozart/README.md).
- `python swd/convert.py --out DIR [--only ID ...] [--package DIR] [--no-tilia] [--audio]`: one TiLiA file per song and performance (216), with a zip package; see [`swd/README.md`](swd/README.md).

## Run the tests

```
pip install -e . pytest
export TILIA=/path/to/tilia                      # defaults to "tilia" on PATH
export DATASET_CONVERTERS_CACHE=/path/to/cache   # defaults to ~/.cache/dataset-converters
export QT_QPA_PLATFORM=offscreen                 # TiLiA runs without a display
pytest
```

The tests download small fixtures from the datasets into `DATASET_CONVERTERS_CACHE` (checked by md5; nothing is committed) and run TiLiA as a subprocess. Tests that need TiLiA skip only when `TILIA` is unset and no `tilia` is on `PATH`. CI (`.github/workflows/ci.yml`) runs the same on Python 3.12.

## Shared code (`common/`)

- `common.runner.run_script(path, *, tilia=None, timeout=1800, check=True)`: runs a TiLiA script headless through `tilia -i cli` (`tilia` defaults to `$TILIA`, then `tilia` on `PATH`) and returns a `ScriptResult` (`ok`, `errors`, `commands`, `output`). TiLiA's CLI always exits with status 0, so success is read from its output: no error text and every command of the script echoed. With `check=True` a failure raises `ScriptError`, which carries the result. It stands in until TiLiA has a non-interactive `tilia run`.
- `common.download.fetch(url, md5, *, cache_dir=None)`: downloads into the cache, reuses a cached file with the right md5, and raises `ChecksumError` (deleting the download) on a mismatch.
- `common.download.fetch_member(zip_url, member, md5, *, cache_dir=None)`: reads one member of a remote zip with HTTP range requests, so large archives are never downloaded whole, and verifies and caches it like `fetch`.
- `common.lint.lint(tla_path, harmony_csvs=())`: checks a converted file's spelling and sections, and returns `{"errors", "warnings", "rules", "examples"}` (counts per rule and the first five findings). Each converter adds it to every item in `summary.json` under `lint`, and its fixture tests require no errors. Errors: a double flat or sharp in front of a Roman numeral; a key with more than seven sharps or flats; a slash bass that is a chord tone under another name (`C#7/F`); two sections that overlap at one level of a hierarchy. Warnings: a root that another letter would fit to the key (A♯ in D minor, for B♭); a slash bass outside the chord (`C/D`), as some styles write for reading convenience. Chords shown as custom text are skipped, since their symbol is an approximation.
- `common.package.build_package(name, files, licence, notes, *, out_dir)`: writes a reproducible `<name>.zip` with the files, a `LICENSE` (from an SPDX id such as `CC-BY-3.0`, `CC-BY-NC-SA-4.0`, `ODbL-1.0`, `MIT`) and a `NOTICE.md`; an unknown id raises `ValueError`.
