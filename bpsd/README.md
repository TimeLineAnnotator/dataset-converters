# Beethoven Piano Sonata Dataset (BPSD) to TiLiA

Create TiLiA files from the audios, scores and annotations in the [Beethoven Piano Sonata Dataset](https://transactions.ismir.net/articles/10.5334/tismir.196).

Produces audio only for the performances which are copyright-free in the EU. Code can be easily adapted to include the rest of the performances.

The `tla` folder contains the derived TiLiA files with no loaded audios. To create files with audios, follow the instructions below.

## Create files with loaded audio
- Clone the repository
- Download the dataset [here](https://zenodo.org/records/12783403)
- Unzip and copy the `Beethoven_Piano_Sonata_Dataset_v2` folder to the same directory where the repository was cloned
- Install the dependencies listed at `requirements.txt`
- Run `python main.py`

A folder named `import_data` will be created, with subdirectories for the pieces and performances, each containing:
- `chords.csv`, `localkey.csv`, `measures.csv`, `structure.csv`: CSVs to imported into the TiliA files
- `import.txt`: a script for the TiLiA CLI, which creates the respective `.tla` files

An `import-all.txt` script will also be created at the repository root. Running it with the TiLiA CLI will create `.tla` for all the performances, overwriting the files in the `tla` directory.

## Running TiLiA CLI scripts

- To start the TiLiA CLI, run the TiLiA executable (or `tilia\main.py`, if you built from source) with the `--interface cli` option
- Run the `script <path to script>` command to execute the script

## For developers
- Before commiting changes to the `tla` files, run `pyhon anonymize_tla.py` to remove references to local paths.

## References
Zeitler, J., Weiß, C., Arifi-Müller, V., & Müller, M. (2024). BPSD: A Coherent Multi-Version Dataset for Analyzing the First Movements of Beethoven’s Piano Sonatas. Transactions of the International Society for Music Information Retrieval, 7(1), 195-212. https://doi.org/10.5334/tismir.196
