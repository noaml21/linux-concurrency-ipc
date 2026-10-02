# Testing and verification

Correctness is tested separately from performance. No test or CI job has a
performance threshold.

## Build targets

All C targets compile with:

```text
-std=c11 -Wall -Wextra -Werror -pedantic
```

```sh
make test            # build and run all C functional tests
make app             # non-optimized development CLI: build/linux-concurrency-ipc
make release         # -O2 benchmark CLI: build/linux-concurrency-ipc-release
make fault-test      # separate IPC_TESTING binary; controlled faults and cleanup
make sanitizer-test  # ASan+UBSan on safe C modes; rebuilds test binaries
make clean           # remove the complete build/ directory
```

The release build uses `-O2` and `-pthread` without machine-specific
optimization flags.

## Test suites

| Suite | Command | What it checks |
|---|---|---|
| C unit tests | `make test` | 13 assertion-based programs: record, validator, I/O, timing, runtime, each synchronization and IPC mode, and the batched ring (all batch sizes through capacity 64, wraparound, partial batches) |
| Fault injection | `make fault-test` | Test-only binary with deterministic producer failure/stall, fork failure, cancellation, slow consumer and parent signals; verifies nonzero exit, child reaping and removal of exact traced IPC objects |
| Sanitizers | `make sanitizer-test` | AddressSanitizer + UndefinedBehaviorSanitizer over the safe-mode C tests |
| Stress | `python3 scripts/stress.py` | 11 large correctness cases against the release binary |
| Lab | `.venv/bin/python -m unittest discover -s tests/lab -v` | 42 Python tests: parsing, validation, statistics, commands, history, real engine runs, Textual Pilot UI |

### Fault injection

`make fault-test` builds `build/linux-concurrency-ipc-fault` with `-DIPC_TESTING`.
Production binaries do not read fault variables or print resource traces. The
fault matrix and what it can and cannot prove are documented in
[Reliability → Fault coverage](RELIABILITY.md#fault-coverage).

### Sanitizers

Intentionally racy `process-unsafe` is excluded from sanitizer correctness tests.
Sanitizers cannot prove interprocess ordering, fairness or complete race
freedom; deterministic faults test selected failure paths. Non-PIE sanitizer
executables avoid address-space shadow mapping collisions; release builds retain
the compiler's default executable model.

### Stress correctness

The larger correctness suite runs with the optimized executable:

```sh
make release
python3 scripts/stress.py
```

It executes each case once, sequentially, with a 120-second timeout per case. It
excludes `process-unsafe` because that mode is intentionally racy. The
synchronization workloads are:

- `threads-mutex`: 8 workers × 250,000 operations;
- `process-sem`: 8 workers × 25,000 operations.

Every IPC stress case uses 8 producers × 50,000 records, or 400,000 records
total. Pipe, FIFO, and shared-memory mailbox are checked once each. The ring is
checked at capacities 1, 2, 8, 64, 256, and 1024.

The runner verifies the returned family, mode, and workload metadata.
Synchronized counters must be exact with zero lost updates. Every IPC case must
receive all expected records, pass validation, and report zero missing,
duplicate, corrupted, and out-of-range records. It stops immediately on a
non-zero exit, malformed output, timeout, or correctness failure; it does not
collect performance data.

### Lab tests

The Python suite uses standard-library `unittest` and Textual Pilot. It includes
parser/validation/statistics/command/history tests, real tiny CLI executions of
all eight mechanisms, and UI workflows for IPC, sync, capacity sweep,
cancellation, history, comparison, export, storage errors, and smaller
terminals. Build the release binary first; real integration tests are required,
not silently skipped.

## Continuous integration

[`.github/workflows/linux.yml`](../.github/workflows/linux.yml) runs on Ubuntu
24.04 for pushes and pull requests to `main`, and can be started manually:

- **compilers** (GCC and Clang): strict build and C tests, fault matrix, CLI
  smoke checks, stress correctness;
- **sanitizers** (GCC and Clang): `make sanitizer-test`;
- **python**: lab tests including Textual Pilot, `./scripts/explore --check`, and
  a bounded reproducible experiment.

## Full local verification

```sh
make clean
make test app release
python3 scripts/stress.py
make fault-test
.venv/bin/python -m unittest discover -s tests/lab -v
./scripts/explore --check
make sanitizer-test
git diff --check
```
