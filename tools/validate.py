"""Offline project checks. Install requirements-dev.txt and Node 20+ first."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("Node 20+ is required for JavaScript syntax checks.", file=sys.stderr)
        return 1
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        *[[node, "--check", str(path)] for path in sorted((ROOT / "web").glob("*.js"))],
    ]
    for command in commands:
        print("+ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
