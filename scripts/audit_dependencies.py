from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if shutil.which("pip-audit") is None:
        print("pip-audit is not installed. Install it with: python -m pip install pip-audit")
        return 2

    return subprocess.run(
        ["pip-audit", "-r", str(PROJECT_ROOT / "requirements.txt")],
        cwd=PROJECT_ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
