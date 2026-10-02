# V2 build log

## Milestone 0 — audit and V1 baseline

- Audited the repository layout, C engine and cleanup paths, CLI contract,
  tests, Makefile, and V1 scripts.
- `make test`: all 11 C test executables passed.
- `make release`: strict C11 release build passed.
- CLI `--help` and all seven modes with 2 workers/producers × 100 items passed;
  IPC validation counters were zero and synchronized counters were exact.
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

## Milestone 2 — execution, history, comparison and export

- Added sequential asyncio subprocess execution, started/completed events, safe
  boundary cancellation, and draining of the active engine on worker cancellation.
- Added original-output run records, UTC/system/engine-digest metadata, validated
  versioned JSON with atomic writes, compatible-run comparisons, and V2 CSVs.
- Ignored `.venv/` and `results/lab/`; existing V1 CSVs remain tracked and untouched.
- `python3 -m unittest discover -s tests/lab -v`: all 19 tests passed, including
  real executions of all seven mechanisms, exact raw-output/parsed-value checks,
  failure records, cancellation, serialization, comparisons, and export.
- `make test`: all 11 C tests passed. The threads-mutex CLI (2 × 100) returned an
  exact observed count and zero lost updates.
- Reviewed the diff: only new lab modules/tests, ignore rules, and this log;
  no changes to the C engine, C tests, V1 scripts, or baseline CSVs.

## Milestone 3 — interactive Textual lab

- Added styled Configure, Live, Results and History tabs; ring capacity sweeps,
  real completion counts, correctness details, sample sparklines, relative median
  bars, raw output inspection, compatible history comparisons, save retry and CSV.
- Added `scripts/explore`, dependency/release guidance and `--check`; pinned
  Textual 8.2.8 in the optional lab requirements, installed in a local `.venv/`.
- All 28 core/integration/presentation/UI tests passed after layout refinement;
  four additional launcher tests passed (32 total). UI tests run real IPC,
  synchronization, and six-capacity sweeps, history/export/compare, cancellation,
  invalid input, storage failure/retry, and keyboard navigation at 60×20.
- Inspected the rendered 80×24 layout and compacted the configuration panels;
  real-result tables are sized to reduce empty space.
- `make test`: all 11 C tests passed. FIFO CLI (2 × 100) passed validation.
  `./scripts/explore --check` passed. Reviewed the staged scope and whitespace;
  C source, C tests, V1 scripts and recorded CSVs remain unchanged.

## Milestone 4 — final review, documentation and release verification

- Documented installation, interaction, architecture, history/CSV schema,
  methodology, workload limits, and cancellation/crash limitations in README;
  added a reproducible demo and actual Textual SVG screen captures.
- Final review tightened required history identity/execution fields and schema
  types, prevented a cancelled-inner-task shutdown loop, retained unsaved results
  on quit/save failure, and added graceful-quit/shutdown regression coverage.
- Final required gates, all passed:
  - `make clean`, `make test` (all 11 C test executables), `make release`.
  - `python3 scripts/stress.py` (all 11 stress cases).
  - `.venv/bin/python -m unittest discover -s tests/lab -v` (34 tests, including
    all seven real modes, sweeps, parsing/raw-value equality, input rejection,
    cancellation/quit, history/export/compare, and 60×20 UI smoke coverage).
  - `python3 scripts/benchmark.py --repetitions 1 --output-dir
    results/lab/v1-verification`: all 11 V1 benchmark cases and both CSVs succeeded.
  - `./scripts/explore --check`, `sh -n scripts/explore`, and local `pip check`.
- Real terminal smoke check: launched `./scripts/explore`, pressed Ctrl+R,
  confirmed the saved run had 12/12 real executions with zero failures, and quit
  cleanly with Ctrl+Q. Documentation capture separately completed 8/8 real executions.
- Reviewed the full diff for shell execution, cancellation, schema errors,
  performance interpretation, dependencies, and scope. The C engine, all C tests,
  Makefile, V1 scripts and original CSV datasets are byte-for-byte unchanged.
- Confirmed virtual environment, build output, Python caches and generated local
  runs/exports are ignored. Only intentional documentation SVGs are tracked.
- Known limits at the end of V2: cancellation drains the current case with no
  hard timeout, unexpected termination may lose an unfinished run, and
  descriptive comparisons do not control CPU frequency, affinity or system load.
