import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from common.runner import run_script
from conftest import BPSD_PERFORMER, BPSD_PIECE

MAIN = Path(__file__).resolve().parents[1] / "main.py"

# sha256 of the CSVs the original converter (commit 9ce87fc) writes for the fixture
CSV_SHA256 = {
    "localkey.csv": "b0e0deacfe3bcf83626c0aa14337de0c7b49fdf0a25a4d7ae436a5324aad508d",
    "structure.csv": "80ab84d2f8f7cc854989cbbdd2ee9a49d317489e66fde7816321432d1129fdfa",
    "measures.csv": "88a3a5d084f98fe276e1b16e571a5c589c666f6f83a61fc364bea0a671ec6207",
    "chords.csv": "6a282299c48f2b6b68d62df436ac25ccdedfba667e6c6fc365e07fb4378cac0d",
}


@pytest.fixture(scope="module")
def converted(bpsd_dataset, tmp_path_factory):
    out = tmp_path_factory.mktemp("bpsd-out")
    subprocess.run(
        [sys.executable, str(MAIN), "--dataset", str(bpsd_dataset), "--pieces", BPSD_PIECE,
         "--performers", BPSD_PERFORMER, "--out", str(out / "import-data"),
         "--tla-dir", str(out / "tla"), "--all-script", str(out / "import-all.txt")],
        check=True, cwd=out,
    )
    return out


def test_csvs_match_the_original_converter(converted):
    folder = converted / "import-data" / BPSD_PIECE / BPSD_PERFORMER
    for name, sha in CSV_SHA256.items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == sha, name
    assert (folder / "import.txt").exists()
    assert (converted / "import-all.txt").read_text().startswith("script ")


def test_import_script_builds_the_tla(converted, tilia):
    script = converted / "import-data" / BPSD_PIECE / BPSD_PERFORMER / "import.txt"
    run_script(script, tilia=tilia)
    data = json.loads((converted / "tla" / f"Beethoven_{BPSD_PIECE}_{BPSD_PERFORMER}.tla").read_text())
    timelines = {t["name"]: t for t in data["timelines"].values() if "name" in t}
    for name in ["Structure", "Measures", "Keys", "Chords", "Score"]:
        assert timelines[name]["components"], name
