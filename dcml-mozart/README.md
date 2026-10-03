Converts a DCML harmonies TSV file into an import script for the TiLiA CLI.

# Usage
Clone the repository and install the dependencies using `pip`:
```
pip install -r requirements.txt
```

Run the `main.py` script with the path to the TSV file as an argument. Assuming you are the same directory as it:
```
python ./main.py <path_to_tsv_file>
```

The script will output five CSV files:
- beats.csv: data for importing a beat timeline with evenly spaced beats;
- cadences.csv: data for importing a marker timeline with the cadence points;
- chords.csv: data for importing a marker timeline with the harmony labels;
- keys.csv: data for importing a marker timeline with the key labels;
- phrases.csv: data for importing a one-leveled hierarchy timeline with the phrase spans.

It will also outuput a text file named `import-script.txt`, which may be used in the Tilia CLI to create a Tilia file from the extracted data. `cd` to the Tilia install location and start it in CLI mode with:
```
source TLA --user-interface cli
```

Wait for the CLI to load, and use the `import` command to load the data and save the Tilia file:
```
import <path_to_tilia_script>
```
