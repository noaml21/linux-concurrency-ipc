# Linux Concurrency & IPC Lab

[![Linux correctness](https://github.com/noaml21/linux-concurrency-ipc/actions/workflows/linux.yml/badge.svg?branch=main)](https://github.com/noaml21/linux-concurrency-ipc/actions/workflows/linux.yml?query=branch%3Amain)

A C11 benchmark engine for Linux synchronization and inter-process communication
that validates every transferred record, with an interactive terminal lab for
running, inspecting and comparing experiments.

![Results tab: pipe, System V ring and batched ring, all passing validation](docs/images/lab-results.svg)

<sub>Real capture of the lab's Results tab: 2 producers × 2,000 records, three
repetitions each. The timings are from a small local run and illustrate the UI;
see the <a href="docs/PERFORMANCE_REPORT.md">performance report</a> for a
controlled comparison.</sub>

## What it explores

| Area | Implementations |
|---|---|
| Synchronization | Intentionally racy shared counter · pthread mutex · System V semaphore |
| Stream IPC | Anonymous pipe · named FIFO, with multiple writers |
| Shared-memory IPC | Capacity-1 mailbox · bounded MPSC ring buffer · producer-batched ring |
| Reliability | Deadlines, cancellation, scoped child reaping, exact resource cleanup, fault injection |
| Analysis | Textual lab: capacity sweeps, seeded matrices, durable history, run comparison, CSV export |

## Highlights

- **Real Linux primitives in C.** `fork`, pthreads, pipes, FIFOs, System V
  semaphores and shared memory, built with `-std=c11 -Wall -Wextra -Werror -pedantic`.
- **Correctness separate from speed.** Every record carries a producer ID,
  sequence number and integrity value. A streaming validator counts missing,
  duplicate, corrupted and out-of-range records, and failed runs never enter
  rate statistics.
- **A semaphore-based ring buffer in shared memory.** Bounded multi-producer /
  single-consumer, with backpressure and per-producer completion. A batched
  variant reserves and publishes N slots per `semtimedop` and runs alongside the
  original ring rather than replacing it.
- **Owner-scoped shutdown.** Deadlines and cancellation are checked at blocking
  points, stalled children escalate from SIGTERM to SIGKILL, and only the exact
  tracked PIDs, IPC IDs and FIFO paths are reaped and removed.
- **Tested failure paths.** A separate test-only build injects producer stalls
  and failures, fork failures and signals, then checks that processes and IPC objects
  are gone.
- **Reproducible experiments.** Seeded interleaved repetitions, warmups, and
  versioned JSON history with exact commands, raw output, engine digest and
  build provenance.

## Quick start

Requires Linux (native or WSL2), GCC, Make and Python 3.10+.

```sh
make release                                          # build the optimized C engine
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lab.txt
./scripts/explore                                     # open the interactive lab
```

Press **Ctrl+R** to run the default experiment. `./scripts/explore --check`
verifies the setup without opening the UI.

The engine also runs on its own, without the lab. Each run prints one
`key=value` line:

```console
$ ./build/linux-concurrency-ipc-release ipc shm-ring 4 20000 8
family=ipc mode=shm-ring producers=4 records_per_producer=20000 capacity=8 expected=80000 received=80000 missing=0 duplicates=0 corrupted=0 out_of_range=0 validation_pass=1 elapsed_seconds=0.685255 records_per_second=116744.877757
```

## How it works

```text
   Textual UI  ·  headless experiment CLI            ipc_lab/  (Python)
                    │
                    ▼
   Orchestration: validate config → spawn engine (no shell)
   → parse output → statistics → JSON history, CSV
                    │
                    ▼
   C benchmark engine: workers · timing · validation · cleanup    src/  (C11)
                    │
                    ▼
   Linux / POSIX: fork, pthreads, pipe, FIFO, System V sem + shm
```

The C engine owns the benchmark semantics: it creates the workers, times the run
with `CLOCK_MONOTONIC`, validates every record and cleans up its own resources.
Python schedules runs, parses the engine's output and stores the results; the UI
contains no IPC or synchronization logic. See [Architecture](docs/ARCHITECTURE.md).

## Example experiments

| Mode | What it shows | Engine command |
|---|---|---|
| `process-unsafe` | Race baseline: lost updates are a valid outcome | `sync process-unsafe 4 100000` |
| `threads-mutex` | pthread mutex around a shared counter | `sync threads-mutex 4 100000` |
| `process-sem` | System V semaphore across processes | `sync process-sem 4 100000` |
| `pipe` / `fifo` | Multiple writers with atomic `PIPE_BUF` records | `ipc pipe 4 20000` |
| `shm-mailbox` | Capacity-1 shared-memory handoff | `ipc shm-mailbox 4 20000` |
| `shm-ring` | Bounded ring: EMPTY / FULL / producer-mutex semaphores | `ipc shm-ring 4 20000 8` |
| `shm-ring-batch` | Ring with batched producer reservation | `ipc shm-ring-batch 4 20000 64 8` |

In the committed 80-execution [ring study](docs/PERFORMANCE_REPORT.md), batching
at capacity 64 raised median throughput 1.83–3.08× over the baseline ring across
four workloads. At capacity 2 the results were mixed (0.85–1.04×).

## Documentation

| Guide | Covers |
|---|---|
| [Usage](docs/USAGE.md) | Setup, UI workflow and keys, headless matrices, C CLI |
| [Demo](docs/DEMO.md) | Five-minute tour including failure injection |
| [Architecture](docs/ARCHITECTURE.md) | Engine layout, record validation, ring protocol, lab and history design |
| [Reliability](docs/RELIABILITY.md) | Lifecycle, cancellation, invariants, fault matrix, limits |
| [Benchmarks](docs/BENCHMARKS.md) | What is timed, how to read results, original V1 dataset |
| [Performance report](docs/PERFORMANCE_REPORT.md) | Baseline vs. batched ring, with raw data |
| [Testing](docs/TESTING.md) | Test suites, stress, sanitizers, CI |
| [Study guide](docs/STUDY_GUIDE.md) | Questions to answer from the code |

Full index: [docs/](docs/README.md).

## Verification

| Check | Command |
|---|---|
| 13 C unit-test programs | `make test` |
| Fault injection and exact cleanup | `make fault-test` |
| ASan + UBSan (safe modes) | `make sanitizer-test` |
| 11 large correctness cases | `python3 scripts/stress.py` |
| 42 Python tests, real engine and Textual UI | `.venv/bin/python -m unittest discover -s tests/lab` |

[GitHub Actions](.github/workflows/linux.yml) runs all of these with GCC and
Clang on Ubuntu 24.04. CI checks correctness only and has no performance
thresholds. Details: [Testing](docs/TESTING.md).

## Scope and limits

- Linux only. Numbers are descriptive measurements on one machine. CPU frequency,
  load and scheduling are not controlled, and per-record latency is not measured.
- Cancellation is cooperative and bounded under normal scheduling. SIGKILL of the
  owner or machine failure cannot guarantee FIFO or System V resource cleanup.

See [Benchmarks](docs/BENCHMARKS.md) and [Reliability](docs/RELIABILITY.md) for
the full caveats.

## Repository layout

```text
src/        C engine: main.c, common/ (records, validator, I/O, timing, runtime), sync/, ipc/
include/    C headers
tests/      C unit tests · lab/ Python and UI tests · reliability/ fault-injection tests
ipc_lab/    Python orchestration, history storage and Textual UI
scripts/    explore launcher, stress and V1 benchmark runners, build provenance
docs/       guides, design notes, performance report and its data
results/    original V1 benchmark dataset (lab output goes to ignored results/lab/)
```
