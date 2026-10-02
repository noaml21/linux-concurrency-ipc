# V2 implementation plan

## Baseline and constraints

The existing C CLI is the sole measurement engine. Preserve `src/`, `include/`,
the C tests, V1 scripts, and recorded CSVs. Add a Python package `ipc_lab/` with
Textual as its only direct runtime dependency, and standard-library unit tests.

## Sequential milestones

0. **Audit and baseline:** inspect the engine, CLI, scripts, and tests; run
   `make test`, `make release`, help, and tiny cases for all seven modes.
1. **Experiment core:** bounded configurations, extensible case expansion
   (including ring capacity sweeps), explicit argument lists, strict output
   parsing, correctness interpretation, and statistics. Test malformed input,
   metadata mismatches, invalid configurations, and failed measurements.
2. **Execution and storage:** sequential asynchronous execution, real case
   events, cancellation between repetitions, versioned JSON history with raw
   output and engine/system metadata, compatible-run comparison, CSV export.
   Test failure paths, cancellation, round trips, and real tiny CLI cases.
3. **Interactive lab:** styled configuration, execution, results, and history
   tabs; validation, capacity sweep, comparison and export; `scripts/explore`.
   Verify with Textual Pilot including real executions and smaller terminals.
4. **Release verification:** setup/architecture/methodology/demo documentation,
   final review and the full verification gates.

Every milestone must pass targeted tests, `make test`, CLI checks, and a scope
review before it is recorded in the build log and committed.

## Design decisions

- `models.py` defines immutable configurations and cases; `parsing.py` validates
  the CLI contract; `analysis.py` aggregates only accepted samples.
- `runner.py` invokes the release binary with `asyncio.create_subprocess_exec`,
  never a shell. UI inputs cannot select an executable or inject arguments.
- Cancellation stops scheduling new cases and drains the current case. The C
  engine owns FIFO and System V resource cleanup and does not have a safe
  forced-termination protocol. Bounded workloads limit normal cancellation
  latency; a stalled engine cannot be forcibly stopped safely by this prototype.
- Progress advances only on actual completed executions. No record-level
  progress is implied by the CLI's single output line.
- Store raw output, errors, parameters, UTC timestamps, platform/CPU count,
  and a binary digest in versioned JSON under ignored `results/lab/`.
- Show median/min/max with sample counts. Incorrect samples are visible but
  excluded from performance summaries. Unsafe-counter measurements are
  explicitly attempted-operation rates, never useful synchronized throughput.
- Use tabs, scrollable forms/tables, a real completion bar, and relative median
  bars. Comparisons require matching workloads, cases, engine, and system
  metadata; observations are descriptive, not statistical significance claims.

## Final gates

Run `make clean`, `make test`, `make release`, `python3 scripts/stress.py`, all
Python tests, real experiments through the TUI, and the unchanged V1 benchmark
script with output isolated under `results/lab/`. Review diffs and ignored
artifacts, and document verification results, limitations, and reproducible
manual demo steps.
