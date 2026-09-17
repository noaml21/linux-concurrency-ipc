"""Friendly optional-dependency and release-binary checks for scripts/explore."""

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Linux Concurrency & IPC Lab — interactive C benchmarks")
    parser.add_argument("--check", action="store_true", help="check setup without opening the terminal UI")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    problems = []
    if sys.version_info < (3, 10):
        problems.append("Python 3.10 or newer is required.")
    if sys.platform != "linux":
        problems.append("This benchmark engine requires Linux (including WSL2).")
    if importlib.util.find_spec("textual") is None:
        problems.append("Textual is missing. From the repository root run:\n  python3 -m venv .venv\n  .venv/bin/python -m pip install -r requirements-lab.txt")
    binary = root / "build/linux-concurrency-ipc-release"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        problems.append("Release binary is missing or not executable. Run:\n  make release")
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 1
    if arguments.check:
        print("Lab ready: Linux, Python, Textual and release engine available.")
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Open ./scripts/explore in an interactive terminal (or use --check).", file=sys.stderr)
        return 1
    from .app import LabApp
    LabApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
