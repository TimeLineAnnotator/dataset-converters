import json

import pytest

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
