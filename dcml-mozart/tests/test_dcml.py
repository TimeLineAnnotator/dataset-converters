import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from common.runner import run_script

MAIN = Path(__file__).resolve().parents[1] / "main.py"

# sha256 of the CSVs the original converter (commit b0dc122) writes for the fixture
CSV_SHA256 = {
    "chords.csv": "7556d2446dbe56cf6286a7bc19c236d2b392fd63fdd106ac0dad01f456cd44da",
    "beats.csv": "a04115f493add3e407f1ee1ee2e34c9abdb410eb29e26613debba868852f1da8",
    "cadences.csv": "573cb10a79668cb4a8b573088c1f378844be51c10fd7cc456885559de6d8ab8b",
    "keys.csv": "4a07cffea86980e784f0ffc51a9bbd88e6e8e8953baf9605c5168b11d036844a",
    "phrases.csv": "5809ffff355e354dfdb9a4e168836c1f3b509f8e9954b2d9a29bddd02aa5487c",
}


@pytest.fixture(scope="module")
def converted(dcml_dataset, tmp_path_factory):
    out = tmp_path_factory.mktemp("dcml-out")
    subprocess.run([sys.executable, str(MAIN), str(dcml_dataset / "harmonies" / "K279-1.tsv")], check=True, cwd=out)
    return out


def test_csvs_match_the_original_converter(converted):
    for name, sha in CSV_SHA256.items():
        assert hashlib.sha256((converted / name).read_bytes()).hexdigest() == sha, name


@pytest.mark.xfail(
    strict=True,
    reason="import-script.txt uses the old syntax 'timeline import csv ...', which TiLiA 0.7.0 rejects "
           "(argparse: invalid choice: 'csv')",
)
def test_import_script_runs(converted, tilia):
    run_script(converted / "import-script.txt", tilia=tilia)
