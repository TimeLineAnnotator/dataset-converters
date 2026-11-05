"""Windows reads and writes text in its code page unless told otherwise, and that has bitten three times: a choro
title, swd's NOTICE, swd's scripts. So no code outside the tests may leave the encoding to the platform."""
import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def default_encoding_calls(source: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("read_text", "write_text"):
                lines.append(node.lineno)
        elif isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
            if not (isinstance(mode, ast.Constant) and "b" in mode.value):
                lines.append(node.lineno)
    return lines


def test_the_check_sees_what_it_should():
    assert default_encoding_calls('p.read_text()\np.write_text("x")\nopen(p)\nopen(p, "w")\n') == [1, 2, 3, 4]
    assert default_encoding_calls('p.read_text(encoding="utf-8")\nopen(p, "rb")\nopen(p, "w", encoding="utf-8")\n') == []


def test_no_code_leaves_the_encoding_to_the_platform():
    tracked = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    found = {}
    for name in tracked.splitlines():
        if "tests/" not in name and name != "conftest.py":
            calls = default_encoding_calls((ROOT / name).read_text(encoding="utf-8"))
            if calls:
                found[name] = calls
    assert not found
