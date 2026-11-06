"""Run TiLiA command scripts without a display."""
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_GREEN = re.compile(r"\x1b\[32m(.*?)\x1b\[39m", re.S)
_RED = re.compile(r"\x1b\[31m(.*?)\x1b\[39m", re.S)
# argparse prints "<prog> <subcommand>: error: <message>"; TiLiA's prog is "TiLiA"
_ARGPARSE_ERROR = re.compile(r"^TiLiA\b[^\n]*?: error: .*$", re.M)


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


@dataclass
class ScriptResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    output: str = ""
    crashed: bool = False  # TiLiA stopped without reporting an error, so the script may not be at fault


class ScriptError(RuntimeError):
    def __init__(self, result: ScriptResult):
        self.result = result
        message = "TiLiA script failed:\n" + "\n".join(result.errors)
        if result.crashed:
            message += "\n\nTiLiA's output ended with:\n" + "\n".join(result.output.splitlines()[-20:])
        super().__init__(message)


def _script_commands(path: Path) -> list[str]:
    commands = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            commands.append(line)
    return commands


def run_script(
    path, *, tilia: str | None = None, timeout: float = 1800, check: bool = True, attempts: int = 5
) -> ScriptResult:
    """Run a TiLiA script (one command per line) through TiLiA's CLI and report how it went.

    TiLiA's CLI always exits with status 0, so success is read from its output: no
    error text, and every command of the script echoed. This is the stand-in until
    TiLiA has a non-interactive ``tilia run``.

    A run where TiLiA stops without reporting an error is repeated from scratch, up to ``attempts``
    runs in all: on Windows, TiLiAs starting at once crash deleting the same old log file. A script
    must therefore be repeatable, which ``save --overwrite`` makes it. Reported errors are not repeated.
    """
    path = Path(path).resolve()
    tilia = tilia or os.environ.get("TILIA") or "tilia"
    for attempt in range(attempts):
        result = _run_once(path, tilia, timeout)
        if result.ok or not result.crashed or attempt == attempts - 1:
            break
        time.sleep(attempt + random.random())  # apart from whatever else is starting
    if check and not result.ok:
        raise ScriptError(result)
    return result


def _run_once(path: Path, tilia: str, timeout: float) -> ScriptResult:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONUTF8", "1")  # scripts and CSVs are UTF-8, whatever this Windows' code page is
    proc = subprocess.run(
        [tilia, "-i", "cli"],
        input=f"script {path}\n",
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )

    errors = [strip_ansi(m).strip() for m in _RED.findall(proc.stdout)]
    errors += [m.group(0).strip() for m in _ARGPARSE_ERROR.finditer(strip_ansi(proc.stderr))]
    commands = [strip_ansi(m).strip() for m in _GREEN.findall(proc.stdout)]

    crashed = False
    expected = _script_commands(path)
    if len(commands) < len(expected):
        crashed = not errors
        # TiLiA echoes a command before running it, so the last echoed one is where it stopped
        where = f"at command {len(commands)} of {len(expected)}: {commands[-1]}" if commands else "before the first command"
        errors.append(f"script stopped {where}")
    output = strip_ansi(proc.stdout) + strip_ansi(proc.stderr)
    return ScriptResult(ok=not errors, errors=errors, commands=commands, output=output, crashed=crashed)
