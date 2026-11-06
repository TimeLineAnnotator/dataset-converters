import json
import os
import stat
import sys

import pytest

import common.runner
from common.runner import ScriptError, run_script


@pytest.fixture
def csvs(tmp_path):
    (tmp_path / "m.csv").write_text("time,label\n1.0,a\n2.5,b\n")
    (tmp_path / "bad.csv").write_text("time,label\n1.0,a\nabc,b\n3.0,c\n")
    (tmp_path / "b.csv").write_text("time\n1\n2\n3\n")
    return tmp_path


def script(tmp_path, name, import_line, tla):
    path = tmp_path / f"{name}.txt"
    path.write_text(
        "# a comment\n\n"
        "metadata set-media-length 10\n"
        "timeline add marker --name M\n"
        f"{import_line}\n"
        f"save {tmp_path / tla} --overwrite\n"
    )
    return path


def test_passing_script(csvs, tilia):
    path = script(csvs, "ok", f"timeline import marker by-time --target-name M --file {csvs / 'm.csv'}", "ok.tla")
    result = run_script(path, tilia=tilia)
    assert result.ok and result.errors == []
    assert len(result.commands) == 4
    assert "\x1b[" not in result.output
    data = json.loads((csvs / "ok.tla").read_text())
    marker = next(t for t in data["timelines"].values() if t.get("name") == "M")
    assert len(marker["components"]) == 2


def test_missing_file_fails(csvs, tilia):
    path = script(csvs, "missing", f"timeline import marker by-time --target-name M --file {csvs / 'nope.csv'}", "missing.tla")
    result = run_script(path, tilia=tilia, check=False)
    assert not result.ok
    assert any("nope.csv" in e for e in result.errors)
    assert not (csvs / "missing.tla").exists()
    with pytest.raises(ScriptError) as exc:
        run_script(path, tilia=tilia)
    assert exc.value.result.errors == result.errors
    assert "nope.csv" in str(exc.value)


def test_bad_row_fails_although_tilia_goes_on(csvs, tilia):
    path = script(csvs, "badrow", f"timeline import marker by-time --target-name M --file {csvs / 'bad.csv'}", "badrow.tla")
    result = run_script(path, tilia=tilia, check=False)
    assert not result.ok
    assert any("abc is not a valid time" in e for e in result.errors)
    assert len(result.commands) == 4 and (csvs / "badrow.tla").exists()


def test_old_import_syntax_fails(csvs, tilia):
    path = script(csvs, "old", f"timeline import csv marker by-time --target-name M --file {csvs / 'm.csv'}", "old.tla")
    result = run_script(path, tilia=tilia, check=False)
    assert not result.ok
    assert any("invalid choice" in e for e in result.errors)
    assert any("stopped" in e and "timeline import csv" in e for e in result.errors)
    with pytest.raises(ScriptError):
        run_script(path, tilia=tilia)


# ---------------------------------------------------------------- with a stand-in for TiLiA
FAKE_TILIA = """
import json, pathlib, sys
here = pathlib.Path(sys.argv[0]).parent
config = json.loads((here / "config.json").read_text())
runs = int((here / "runs").read_text()) + 1 if (here / "runs").exists() else 1
(here / "runs").write_text(str(runs))
if runs <= config["crashes"]:
    print("Traceback (most recent call last):", file=sys.stderr)
    print("FileNotFoundError: [WinError 2] tilia/log.py", file=sys.stderr)
    sys.exit(1)
path = sys.stdin.read().removeprefix("script ").strip()
if config.get("error"):
    print("\\x1b[31m" + config["error"] + "\\x1b[39m")
    sys.exit(0)
for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#"):
        print("\\x1b[32m" + line.strip() + "\\x1b[39m")
"""


@pytest.fixture
def fake_tilia(tmp_path, monkeypatch):
    """A TiLiA that crashes as it starts the first ``crashes`` times; returns (path, runs())."""
    monkeypatch.setattr(common.runner.time, "sleep", lambda s: None)
    (tmp_path / "fake.py").write_text(FAKE_TILIA)

    def make(crashes=0, error=None):
        (tmp_path / "config.json").write_text(json.dumps({"crashes": crashes, "error": error}))
        if os.name == "nt":
            path = tmp_path / "fake.cmd"
            path.write_text(f'@"{sys.executable}" "{tmp_path / "fake.py"}" %*\n')
        else:
            path = tmp_path / "fake.sh"
            path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{tmp_path / "fake.py"}" "$@"\n')
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return str(path), lambda: int((tmp_path / "runs").read_text())

    return make


@pytest.fixture
def one_command(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("metadata set-media-length 10\n")
    return path


def test_a_crash_at_startup_is_repeated(fake_tilia, one_command):
    tilia, runs = fake_tilia(crashes=2)
    result = run_script(one_command, tilia=tilia)
    assert result.ok and result.commands == ["metadata set-media-length 10"] and runs() == 3


def test_repeated_crashes_give_up_and_say_why(fake_tilia, one_command):
    tilia, runs = fake_tilia(crashes=99)
    with pytest.raises(ScriptError) as exc:
        run_script(one_command, tilia=tilia, attempts=3)
    assert runs() == 3 and exc.value.result.crashed
    assert "before the first command" in str(exc.value) and "FileNotFoundError: [WinError 2]" in str(exc.value)


def test_an_error_tilia_reports_is_not_repeated(fake_tilia, one_command):
    tilia, runs = fake_tilia(error="no such timeline")
    result = run_script(one_command, tilia=tilia, check=False)
    assert not result.ok and not result.crashed and runs() == 1
    assert "no such timeline" in result.errors


def test_script_with_non_ascii_text_on_any_code_page(fake_tilia, tmp_path):
    # read as cp1252, the "\\xc1" of "\u00c1" stops at byte 0x81
    tilia, _ = fake_tilia()
    path = tmp_path / "s.txt"
    path.write_text("metadata set title \u00c1gua de Beber \u00cdndio\n", encoding="utf-8")
    assert run_script(path, tilia=tilia).commands == ["metadata set title \u00c1gua de Beber \u00cdndio"]
