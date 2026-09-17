# V2 build log

## Milestone 0 — audit and V1 baseline

- Read and preserved the supplied `AGENTS.md`; audited the repository layout,
  C engine and cleanup paths, CLI contract, tests, Makefile, and V1 scripts.
- `make test`: all 11 C test executables passed.
- `make release`: strict C11 release build passed.
- CLI `--help` and all seven modes with 2 workers/producers × 100 items passed;
  IPC validation counters were zero and synchronized counters were exact.
- Confirmed the current branch is `v2/interactive-benchmark-lab` and there were
  no tracked modifications. The supplied untracked `AGENTS.md` is included
  unchanged as the repository's development policy.
- Added `docs/V2_PLAN.md`. No engine, V1 script, or baseline data changes.

## Milestone 1 — experiment core

- Added immutable bounded configurations, explicit argument construction, and
  ring-capacity sweep expansion in `ipc_lab/models.py`.
- Added strict output parsing, metadata/counter consistency checks, separate
  PASS/FAIL/RACY interpretation, and statistics that exclude incorrect samples.
- `python3 -m unittest discover -s tests/lab -v`: 10 tests passed, including
  injection-like inputs, malformed/nonfinite output, statistics and sweeps.
- `make test`: all 11 C tests passed. A real shm-ring CLI case (2 × 100,
  capacity 8) passed with all correctness counters zero.
- Reviewed staged scope and whitespace: only the new Python core/tests and this
  log changed; the C engine and V1 scripts/data remain untouched.
