#!/usr/bin/env python3
"""Write provenance for the binary actually built; never inspect environment secrets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

binary, compiler, flags = sys.argv[1:]
path = Path(binary)
def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

metadata = {
    "engine_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "build_commit": git("rev-parse", "HEAD"),
    "build_dirty": str(bool(git("status", "--porcelain", "--untracked-files=normal"))).lower(),
    "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
    "compiler_flags": flags,
}
path.with_suffix(".build.json").write_text(json.dumps(metadata, indent=2) + "\n")
