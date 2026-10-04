"""Shared fixtures. Dataset files are downloaded into the cache, never stored in the repository."""
import json
import os
import shutil

import pytest

from common.download import fetch, fetch_member

BPSD_ZIP = "https://zenodo.org/records/12783403/files/Beethoven_Piano_Sonata_Dataset_v2.zip?download=1"
BPSD_ROOT = "Beethoven_Piano_Sonata_Dataset_v2"
BPSD_PIECE = "Op049No2-01"
BPSD_PERFORMER = "AS35"
BPSD_MEMBERS = {
    f"2_Annotations/ann_score_localkey/Beethoven_{BPSD_PIECE}.csv": "8f402e187774d10d147806f2e9083413",
    f"2_Annotations/ann_score_structureFine/Beethoven_{BPSD_PIECE}.csv": "29c3381726e0c39d537a88b6b27c9b98",
    f"2_Annotations/ann_score_structureCoarse/Beethoven_{BPSD_PIECE}.csv": "f96359f196a03e29dfc0ea773e8badc9",
    f"2_Annotations/ann_score_chord/Beethoven_{BPSD_PIECE}.csv": "3e3ec606977ba9663d74755186f3d599",
    f"2_Annotations/ann_audio_measure/Beethoven_{BPSD_PIECE}_{BPSD_PERFORMER}.csv": "ffcbc215fd3563cec6b1c6d4858908ca",
    f"1_Audio/Beethoven_{BPSD_PIECE}_{BPSD_PERFORMER}.wav": "644aff6048ca5bb537d74133fa7371dd",
    f"0_RawData/score_xml_unfolded/Beethoven_{BPSD_PIECE}.xml": "dd9e44c4c43a166597829262a0002bc9",
}

DCML_BASE = "https://raw.githubusercontent.com/DCMLab/mozart_piano_sonatas/fe55f8545e976e640965ef0b5ae0ed3d32431464/"
DCML_FILES = {
    "harmonies/K279-1.tsv": "71d330defb710bc47b3fbb63d80576ca",
    "measures/K279-1.tsv": "95ea4f8fd741438456a1a9f6be0ac710",
}


@pytest.fixture(scope="session")
def tilia():
    """Path of the TiLiA executable; tests that need it skip only when none is available."""
    path = os.environ.get("TILIA") or shutil.which("tilia")
    if not path:
        pytest.skip("TILIA is unset and no 'tilia' is on PATH")
    return path


@pytest.fixture(scope="session")
def tilia_keeps_harmony_display(tilia, tmp_path_factory):
    """Whether this TiLiA's harmony CSV import keeps display_mode and custom_text.

    Releases up to 0.7.0 parse those columns and drop them; TimeLineAnnotator/desktop#631 fixes that.
    """
    from common.runner import run_script

    d = tmp_path_factory.mktemp("display-probe")
    (d / "h.csv").write_text("harmony_or_key,time,symbol,display_mode,custom_text\nharmony,0,C,custom,probe\n")
    (d / "s.txt").write_text(
        "metadata set-media-length 4\ntimelines add harmony --name H\n"
        f"timelines import harmony by-time --target-name H --file {d / 'h.csv'}\nsave {d / 'p.tla'} --overwrite\n")
    run_script(d / "s.txt", tilia=tilia)
    data = json.loads((d / "p.tla").read_text())
    return any(c.get("custom_text") == "probe" for t in data["timelines"].values() if t.get("name") == "H"
               for c in t["components"].values())


@pytest.fixture(scope="session")
def bpsd_dataset(tmp_path_factory):
    """The BPSD fixture laid out like the unzipped dataset; returns the dataset folder."""
    root = tmp_path_factory.mktemp("bpsd") / BPSD_ROOT
    for member, md5 in BPSD_MEMBERS.items():
        src = fetch_member(BPSD_ZIP, f"{BPSD_ROOT}/{member}", md5)
        dst = root / member
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return root


@pytest.fixture(scope="session")
def dcml_dataset(tmp_path_factory):
    """The DCML fixture laid out as <root>/harmonies and <root>/measures; returns the root."""
    root = tmp_path_factory.mktemp("dcml")
    for rel, md5 in DCML_FILES.items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fetch(DCML_BASE + rel, md5), dst)
    return root
