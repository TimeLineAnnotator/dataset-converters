import json

from common.roles import set_roles


def test_set_roles_adds_metadata_and_reports_missing(tmp_path):
    path = tmp_path / "a.tla"
    data = {"timelines": {"0": {"kind": "Slider"},
                          "1": {"kind": "Hierarchy", "name": "Structure", "components": {}},
                          "2": {"kind": "Harmony", "name": "Harmony", "metadata": {"author": "X"}}}}
    path.write_text(json.dumps(data), encoding="utf-8")
    missing = set_roles(path, {"Structure": {"role": "form"}, "Harmony": {"role": "harmony"},
                               "Cadences": {"role": "cadences"}})
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["timelines"]["1"]["metadata"] == {"role": "form"}
    assert saved["timelines"]["2"]["metadata"] == {"author": "X", "role": "harmony"}
    assert "metadata" not in saved["timelines"]["0"]
    assert missing == ["Cadences"]
