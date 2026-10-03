import pandas as pd
import fractions
import argparse
from pathlib import Path


# get path argument
parser = argparse.ArgumentParser()
parser.add_argument('path')
args = parser.parse_args()

df = pd.read_csv(args.path, sep="\t")


# rename columns to match tilia csv format
df["fraction"] = df["mn_onset"].apply(lambda x: float(fractions.Fraction(x)))
df["measure"] = df["mn"]


# HARMONIES.CSV
chords = df[["measure", "fraction", "chord"]].copy()
chords.rename(columns={"chord": "label"}, inplace=True)
chords.to_csv("chords.csv")


# MEASURES.CSV
measure_count = chords["measure"].iloc[
    -1
]  # presupposes the existence of at least one chord symbol in the last measure
beats_per_measure = int(
    df["timesig"].iloc[-1].split("/")[0]
)  # Presupposes a constant time signature
# Getting measure info from the 'measures.tsv' would be more robust.
beats = pd.DataFrame(
    [n + 1 for n in range(measure_count * beats_per_measure)], columns=["time"]
)
beats.to_csv("beats.csv")


# CADENCES.CSV
cadences = df[["measure", "fraction", "cadence"]].copy()
cadences.dropna(subset=["cadence"], inplace=True)
cadences.rename(columns={"cadence": "label"}, inplace=True)
cadences.to_csv("cadences.csv")


# KEYS.CSV
# find key changes
curr_key = df["localkey"][0]
curr_key_start = 0

ranges = []
for i, key in enumerate(df["localkey"]):
    if key != curr_key:
        ranges.append((curr_key_start, curr_key))
        curr_key = key
        curr_key_start = i
ranges.append((curr_key_start, curr_key))

# create df with key changes
data = [(df["measure"][i], df["fraction"][i], key) for i, key in ranges]
keys = pd.DataFrame(data, columns=["measure", "fraction", "key"])
keys.rename(columns={"key": "label"}, inplace=True)
keys.to_csv("keys.csv")


# PHRASES.CSV
ranges = []
curr_phrase = []
before_first_phrase = True
for i, value in enumerate(df["phraseend"]):
    if value == "{":
        curr_phrase = [df["measure"][i], df["fraction"][i]]
    elif value == "}":
        curr_phrase += [df["measure"][i], df["fraction"][i]]
        ranges.append(curr_phrase)
    elif value == "}{":
        curr_phrase += [df["measure"][i], df["fraction"][i]]
        ranges.append(curr_phrase)
        curr_phrase = [df["measure"][i], df["fraction"][i]]

phrases = pd.DataFrame(
    ranges,
    columns=["start", "start_fraction", "end", "end_fraction"]
)
phrases["level"] = 1
phrases.to_csv("phrases.csv")

# get measure info

mozart_sonatas_path = Path(args.path).parents[1]
measures_path = Path(mozart_sonatas_path, 'measures', Path(args.path).name)

df = pd.read_csv(measures_path, sep="\t")
beats_per_measure = int(df['timesig'][0].split('/')[1])
beat_count = len(df) * beats_per_measure

# IMPORT-SCRIPT.TXT

script = f"""timeline add hierarchy --name Phrases --height 40
timeline add beat --name Measures --beat-pattern {beats_per_measure}
timeline add marker --name Keys
timeline add marker --name Harmonies

metadata set-media-length {beat_count}
timeline import csv beat --target-name Measures --file {Path('beats.csv').resolve()}
timeline import csv marker by-measure --target-name Harmonies --reference-tl-name Measures --file {Path('chords.csv').resolve()}
timeline import csv marker by-measure --target-name Keys --reference-tl-name Measures --file {Path('keys.csv').resolve()}
timeline import csv hierarchy by-measure --target-name Phrases --reference-tl-name Measures --file {Path('phrases.csv').resolve()}

save {Path(str(Path(args.path).stem) + '-converted.tla').resolve()}"""

with open('import-script.txt', 'w') as f:
    f.write(script)



