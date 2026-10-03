import itertools
from pathlib import Path

import pandas as pd


def convert_measures(metric_series):
    # Split into whole and decimal parts
    whole = metric_series.astype(int)
    decimal = metric_series.mod(1).round(2)

    return whole, decimal


def process_fine_df(df):
    """Process the fine structure file and return level 1 rows"""
    # Filter rows that do not describe a fine structure
    df = df[df['structure'].str.contains(":")]

    # Remove prefix before ":" and clean labels
    df['label'] = df['structure'].str.split(':').str[-1].str.strip()

    # Convert times
    start_whole, start_frac = convert_measures(df['start'])
    end_whole, end_frac = convert_measures(df['end'])

    return pd.DataFrame({
        'start': start_whole,
        'start_fraction': start_frac,
        'end': end_whole,
        'end_fraction': end_frac,
        'label': df['label'],
        'level': 1
    })


def process_coarse_df(df):
    # Clean labels
    df['label'] = df['structure'].str.strip()

    # Convert times
    start_whole, start_frac = convert_measures(df['start'])
    end_whole, end_frac = convert_measures(df['end'])

    return pd.DataFrame({
        'start': start_whole,
        'start_fraction': start_frac,
        'end': end_whole,
        'end_fraction': end_frac,
        'label': df['label'],
        'level': 2
    })


def process_measures_df(df):
    result = pd.DataFrame({
        'time': df['time'],
        "measure": df['measure'].astype(int),
    })
    if df['measure'].iat[-1] % 1 != 0:
        result['measure'].iat[-1] += 1
    return result


def process_localkey_df(df):
    return pd.DataFrame({
        'measure': df['start'].astype(int),
        "label": df['localkey'],
    })


def process_chords_df(df):
    start_measures, start_fractions = convert_measures(df['start'])

    return pd.DataFrame({
        'measure': start_measures,
        'fraction': start_fractions,
        'label': df['roman'],
    })


def get_import_script(filename, media, measures, keys, structure, chords, score, metadata):
    script = ""
    for key, value in metadata.items():
        script += f'metadata set "{key}" "{value}"\n'
    script += f"""\nload-media {media}
    
timeline add hierarchy --name Structure --height 60 
timeline add beat --name Measures --beat-pattern 1 
timeline add marker --name Keys
timeline add marker --name Chords
timeline add score --name Score

timeline import beat --target-name Measures --file {measures}
timeline import marker by-measure --target-name Keys --reference-tl-name Measures --file {keys}
timeline import marker by-measure --target-name Chords --reference-tl-name Measures --file {chords}
timeline import hierarchy by-measure --target-name Structure --reference-tl-name Measures --file {structure}
timeline import score --target-name Score --reference-tl-name Measures --file {score}

save {filename} --overwrite
"""
    return script


dataset_path = Path(r"./Beethoven_Piano_Sonata_Dataset_v2")
pieces = [
    "Op002No1-01",
    "Op002No2-01",
    "Op002No3-01",
    "Op007-01",
    "Op010No1-01",
    "Op010No2-01",
    "Op010No3-01",
    "Op013-01",
    "Op014No1-01",
    "Op014No2-01",
    "Op022-01",
    "Op026-01",
    "Op027No1-01",
    "Op027No2-01",
    "Op028-01",
    "Op031No1-01",
    "Op031No2-01",
    "Op031No3-01",
    "Op049No1-01",
    "Op049No2-01",
    "Op053-01",
    "Op054-01",
    "Op057-01",
    "Op078-01",
    "Op079-01",
    "Op081a-01",
    "Op090-01",
    "Op101-01",
    "Op106-01",
    "Op109-01",
    "Op110-01",
    "Op111-01"
]


def get_metadata(piece, performer_name):
    opus = piece[:5].replace("0", "").replace("Op", "Op. ")
    if "No" in piece:
        number = piece[5:8].replace("No", "No. ")
    else:
        number = None
    movement = piece[-2:]
    movement_to_name = {
        "01": "i",
        "02": "ii",
        "03": "iii",
    }
    title = f"{opus}, {number + ', ' if number is not None else ""}{movement_to_name[movement]}"
    return {
        "title": title,
        "performer": performer_name,
        "composer": "L. v. Beethoven",
        "recording license": "Public Domain (EU)",
        "analysis license": "CC BY 3.0",
        "corpus": r"<a href=\"https://transactions.ismir.net/articles/10.5334/tismir.196\">Beethoven Piano Sonatas Dataset</a>",
        "notes": r"The Beethoven Piano Sonata Dataset (BPSD) is a multi-version dataset focusing on the first movements of Beethoven's 32 piano sonatas.<br><br>It is authored by:<br>Zeitler, J., Weiß, C., Arifi-Müller, V. and Müller, M. (2024) 'BPSD: A Coherent Multi-Version Dataset for Analyzing the First Movements of Beethoven's Piano Sonatas', <i>Transactions of the International Society for Music Information Retrieval</i>, 7(1), p. 195-212. Available at: https://doi.org/10.5334/tismir.196.<br><br>The recordings by Artur Schnabel, Friedrich Gulda, Fritz Jank and Wilhelm Kempff are in the <strong>public domain  in the EU </strong>. We do not  guarantee their copyright status in other countries.",
        "media_storage_type": "staticfiles",  # keys for uploading to the website database
        "media_url": fr"media/bpsd/Beethoven_{piece}_{performer_code}.mp3",  # keys for uploading to the website database
    }


performers = [
    ("AS35", "Artur Schnabel"),
    ("FG58", "Friedrich Gulda"),
    ("FJ62", "Fritz Jank"),
    ("WK64", "Wilhelm Kempff"),
]

script_paths = []

for (performer_code, performer_name), piece in itertools.product(performers, pieces):
    filename = Path(f"Beethoven_{piece}.csv")
    filename_performer = Path(f"Beethoven_{piece}_{performer_code}.csv")

    recording = dataset_path / "1_Audio" / filename_performer.with_suffix(".wav")
    score = dataset_path / "0_RawData" / "score_xml_unfolded" / filename.with_suffix(".xml")

    annotations_dir = dataset_path / "2_Annotations"
    localkey = (annotations_dir / "ann_score_localkey" / filename)
    structure_fine = (annotations_dir / "ann_score_structureFine" / filename)
    structure_coarse = (annotations_dir / "ann_score_structureCoarse" / filename)
    chords = (annotations_dir / "ann_score_chord" / filename)
    measures = (annotations_dir / "ann_audio_measure" / filename_performer)

    localkey_df = process_localkey_df(pd.read_csv(localkey, delimiter=';'))
    structure_fine_df = process_fine_df(pd.read_csv(structure_fine, delimiter=';'))
    structure_coarse_df = process_coarse_df(pd.read_csv(structure_coarse, delimiter=';'))
    structure_df = pd.concat([structure_fine_df, structure_coarse_df])
    chords_df = process_chords_df(pd.read_csv(chords, delimiter=';'))
    measures_df = process_measures_df(pd.read_csv(measures, delimiter=';'))

    output_dir = Path("./import-data", piece, performer_code)
    tla_dir = Path("tla")

    output_dir.mkdir(parents=True, exist_ok=True)
    tla_dir.mkdir(parents=True, exist_ok=True)

    localkey_output = output_dir / "localkey.csv"
    structure_output = output_dir / "structure.csv"
    measures_output = output_dir / "measures.csv"
    chords_output = output_dir / "chords.csv"

    localkey_df.to_csv(localkey_output, index=False)
    structure_df.to_csv(structure_output, index=False)
    measures_df.to_csv(measures_output, index=False)
    chords_df.to_csv(chords_output, index=False)

    metadata = get_metadata(piece, performer_name)

    import_script = get_import_script(
        (tla_dir / filename_performer).resolve().with_suffix(".tla"),
        recording.resolve(),
        measures_output.resolve(),
        localkey_output.resolve(),
        structure_output.resolve(),
        chords_output.resolve(),
        score.resolve(),
        metadata
    )

    with open(output_dir / "import.txt", "w") as f:
        f.write(import_script)

    script_paths.append(str((output_dir / "import.txt").resolve()))

with open("import-all.txt", "w") as f:
    for path in script_paths:
        f.write(f"script {path}\n")
        f.write("clear --force\n")
