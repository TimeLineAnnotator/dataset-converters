# Beethoven Piano Sonata Dataset (BPSD) to TiLiA

Create TiLiA files from the audios, scores and annotations in the [Beethoven Piano Sonata Dataset](https://transactions.ismir.net/articles/10.5334/tismir.196).

Produces audio only for the performances which are copyright-free in the EU. Code can be easily adapted to include the rest of the performances.

## Create files
- Clone the repository and install it from its root (`pip install -e .`), which installs `pandas`
- Download the dataset [here](https://zenodo.org/records/12783403), unzip it, and note the path of the `Beethoven_Piano_Sonata_Dataset_v2` folder
- From the repository root, run `python bpsd/main.py`

By default the converter reads `./Beethoven_Piano_Sonata_Dataset_v2` and converts all 32 pieces for the four performers. Options:
- `--dataset`: folder of the unzipped dataset (default `./Beethoven_Piano_Sonata_Dataset_v2`)
- `--pieces`: pieces to convert, for example `Op049No2-01` (default: all 32)
- `--performers`: performer codes (default: `AS35 FG58 FJ62 WK64`)
- `--out`: folder for the generated files (default `./import-data`)
- `--tla-dir`: folder the scripts save the `.tla` files to (default `tla`)
- `--all-script`: script that runs every import script (default `import-all.txt`)

The `--out` folder will contain subdirectories for the pieces and performances, each with:
- `chords.csv`, `localkey.csv`, `measures.csv`, `structure.csv`: CSVs to be imported into the TiLiA files
- `import.txt`: a script for the TiLiA CLI, which creates the respective `.tla` file

The `--all-script` file runs all the `import.txt` scripts in turn. Running it with the TiLiA CLI creates a `.tla` for every performance in the `--tla-dir` folder.

## Running TiLiA CLI scripts

- To start the TiLiA CLI, run the TiLiA executable (or `tilia\main.py`, if you built from source) with the `--interface cli` option
- Run the `script <path to script>` command to execute the script
- Or, from Python, use `common.runner.run_script(path)`, which runs the script headless and reports errors

`anonymize_tlas.py` removes local paths from the `.tla` files in the `tla` folder.

## References
Zeitler, J., Weiß, C., Arifi-Müller, V., & Müller, M. (2024). BPSD: A Coherent Multi-Version Dataset for Analyzing the First Movements of Beethoven’s Piano Sonatas. Transactions of the International Society for Music Information Retrieval, 7(1), 195-212. https://doi.org/10.5334/tismir.196
