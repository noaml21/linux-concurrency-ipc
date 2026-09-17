# Linux Concurrency & IPC Benchmark

This project is a C/Linux experimental suite for comparing concurrency and inter-process communication mechanisms under common workloads while validating correctness separately from performance. It targets Linux/POSIX APIs and builds with strict C11 compiler warnings.

The synchronization experiments include:

- an intentionally unsafe multi-process shared counter;
- a shared counter protected by a pthread mutex;
- a shared counter protected by a System V semaphore.

The IPC experiments use multiple producer processes and one consumer process to transport deterministic records through:

- an anonymous pipe;
- a named FIFO;
- a capacity-1 System V shared-memory mailbox;
- a bounded System V shared-memory ring buffer.

## Interactive benchmark lab (V2)

**Linux Concurrency & IPC Lab** adds a Textual terminal interface over the same
C release executable. Configure experiments, watch real execution progress,
inspect correctness and throughput, sweep ring capacities, revisit local runs,
compare compatible experiments, and export summaries. All V1 commands and CSV
workflows below remain available without installing Textual.

### Setup and launch

The lab requires Linux (including WSL2), GCC, Make, and Python **3.10+** with
venv/pip support. From the repository root:

```sh
make release
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lab.txt
./scripts/explore --check
./scripts/explore
```

The launcher prefers `.venv/bin/python`, otherwise it uses `python3` from PATH.
It prints setup guidance when Textual or the release binary is missing. It does
not install dependencies or build binaries automatically. An interactive terminal
is required; 100×32 or larger is comfortable, 80×24 is supported, and a 60×20
keyboard smoke test covers smaller terminals. Scroll panels to reveal additional
controls and details; tables also scroll horizontally.

### Interactive workflow

1. **Configure:** choose IPC or synchronization, then select mechanisms with Space.
   Set workers/producers, items **per worker/producer**, repetitions, and ring
   capacity. The default runs the four IPC mechanisms with 2 producers × 2,000
   records, three times each. Validation explains invalid or excessive workloads.
2. **Sweep:** enable “Sweep shm-ring capacity” to select the ring and replace its
   single capacity with `1, 2, 8, 64, 256, 1024`. You can edit the comma-separated
   capacities (at most eight distinct values). Other selected modes run once per
   repetition at the same workload, without the capacity dimension.
3. **Live:** Run or Ctrl+R starts sequential background execution. The app shows
   the current mechanism/repetition, elapsed wall time, actual completed
   executions, failures and the last correctness result. Progress advances only
   when the engine returns; it is not a record-level estimate.
4. **Results:** select a row to see validation counters, expected and observed
   counts, accepted-sample sparkline, and the original engine output. The table
   shows median/min/max throughput and accepted/planned sample count (`n`).
   Export summary CSV writes a separate V2 CSV under `results/lab/exports/`.
5. **History:** select a saved run and Open it. To compare, Pin baseline, select
   a different run, then Compare. Both must be complete without failures, with
   identical configuration, recorded system metadata, and engine digest.

Tab/Shift+Tab move focus, arrows move through tables and selections, and Space
changes a checkbox or selected mechanism. Ctrl+X requests cancellation;
Ctrl+Q (or Ctrl+C) requests a safe quit. The default command palette is also
available with Ctrl+P.

**Cancellation finishes the current execution and skips all remaining ones.**
The C engine owns FIFO/System V IPC cleanup and child reaping. Its existing CLI
has no cooperative mid-execution cancellation protocol, so the lab never kills
it to simulate immediate cancellation. Quit also waits for cleanup and history
saving. A genuinely stalled engine can therefore delay cancellation indefinitely;
there is no hard timeout. The UI remains responsive and labels long executions.
Force-closing the terminal or killing the app cannot guarantee cleanup or saving.

### Interpretation and limits

- IPC rates are records/sec. Correctness requires every expected record exactly
  once, no corruption, and no out-of-range records. Counter details and CSV
  counters are **sums across parsed repetitions**, including incorrect ones.
- Synchronized counters require observed = expected and zero lost updates.
  `process-unsafe` is always labeled **RACY**, even if no loss happens in a run.
  Its reported rate is **attempted operations/sec**, not useful synchronized
  throughput; it is excluded from the common relative-performance bar scale.
- Invalid output and nonzero exits are errors. Parsed correctness failures remain
  visible but are excluded from rate statistics. A cancelled experiment retains
  completed samples, and unexecuted cases display NOT RUN. A failing case can
  still have accepted samples; always inspect its state and sample count.
- Median bars are relative to accepted medians in that run. Sparklines show
  accepted repetitions in execution order. Min/max describe spread, not a
  confidence interval. Tiny demo workloads emphasize startup/scheduling overhead.
- The lab runs cases sequentially, grouped by mechanism/capacity, without warmup,
  randomization, CPU affinity, or frequency control. System metadata is useful
  context, not proof of identical hardware/load. Comparisons make no statistical
  significance or universal performance claims.
- UI limits: 1–32 workers/producers, 1–100,000 items each, at most 200,000 items
  per execution, 1–15 repetitions, capacities 1–32,767, at most 90 executions and
  5,000,000 configured items per experiment. These limits do not change the C CLI.

### Architecture and stored data

```text
scripts/explore → ipc_lab/__main__.py → app.py + lab.tcss
                                         ↓
models.py → runner.py → existing C release CLI → parsing.py
                 ↓                                  ↓
             records.py ←────────────────────── analysis.py
                 ↓                                  ↓
             storage.py                       presentation.py
        results/lab/*.json                    Textual dashboard
        results/lab/exports/*.csv
```

`models.py` validates immutable configurations and expands cases, allowing future
sweep dimensions without adding benchmark logic to the UI. `runner.py` constructs
explicit argument lists and uses `asyncio.create_subprocess_exec` without a shell.
Only the C engine measures time, performs operations, and validates records.
`parsing.py` checks its complete key=value contract and workload metadata;
`analysis.py` computes descriptive statistics. The UI renders results and handles
interaction; it does not implement IPC or synchronization algorithms.

Each run JSON has `schema_version: 1`, a unique run ID, UTC start/finish timestamps,
full configuration (including the sweep), cancellation state, OS/kernel/architecture,
CPU count, Python version, release-engine name and SHA-256, and every attempted
case with its repetition, stdout, stderr, exit code or launch error. Results are
reparsed on load; aggregate values are not trusted from disk. The schema and
schedule are validated, and unreadable files are reported without preventing
other history from loading. Writes use a temporary sibling file and atomic rename.
History is saved when a run finishes or is cancelled; unexpected app termination
before that point can lose that run. Save failures retain results in the app with
a retry button. Generated history, exports, and `.venv/` are ignored by Git.

To reproduce a saved experiment, use its configuration in Configure and compare
the recorded engine digest and environment metadata. Preserve the JSON alongside
its exported CSV: the JSON contains the raw evidence and system metadata. Existing
`results/benchmark_raw.csv`, `results/benchmark_summary.csv`, and
`scripts/benchmark.py` are independent of the lab and retain their V1 format.

### Lab tests and demo

```sh
make test
make release
.venv/bin/python -m unittest discover -s tests/lab -v
python3 scripts/stress.py
```

The Python suite uses standard-library unittest and Textual Pilot. It includes
parser/validation/statistics/command/history tests, real tiny CLI executions of
all seven mechanisms, and UI workflows for IPC, sync, capacity sweep, cancellation,
history, comparison, export, storage errors, and smaller terminals. Build the
release binary first; real integration tests are required, not silently skipped.
See [the reproducible demo](docs/V2_DEMO.md), [implementation plan](docs/V2_PLAN.md),
and [milestone verification log](docs/V2_BUILD_LOG.md).

## Key technical ideas

Each producer emits records identified by a producer ID and sequence number. `record_make()` derives a deterministic integrity value from those fields, allowing the consumer to detect data corruption without storing a reference copy of every record.

The streaming validator tracks expected, received, and unique records and reports missing, duplicate, corrupted, and out-of-range records. It uses one byte of tracking state per expected record. IPC infrastructure success and record validation are deliberately separate: a transport can complete successfully while still reporting `validation_pass=0` if its data is incorrect.

The common I/O layer handles partial reads and writes, retries operations interrupted by `EINTR`, and distinguishes a complete object, clean EOF before an object, and a partial-object/error condition. Records sent through pipes and FIFOs are compile-time checked to fit within `PIPE_BUF`, preserving atomic writes between producers.

Elapsed time is measured with `clock_gettime(CLOCK_MONOTONIC)`. Process and System V IPC paths explicitly create, close, detach, reap, remove, and free their resources on success and failure paths. Semaphore-based producer/consumer modes block in the kernel rather than busy-waiting.

The `process-unsafe` synchronization mode is intentionally different: each child performs an unsynchronized read-modify-write on one shared counter. Lost updates are a valid outcome and make this mode a race-condition baseline, not a correct synchronization strategy.

## Bounded shared-memory ring buffer

The main IPC component is a bounded, multi-producer, single-consumer ring in a System V shared-memory segment. The shared layout contains wrapped `head` and `tail` indices followed by a capacity-sized array of message slots.

Messages have two types:

- `RING_RECORD` carries one `record_t`;
- `RING_DONE` carries the ID of a producer that has completed.

The semaphore set contains exactly three semaphores:

- `EMPTY`: number of slots available to producers;
- `FULL`: number of messages available to the consumer;
- `PRODUCER_MUTEX`: serializes producer writes and updates to `tail`.

```text
Producer:
  wait(EMPTY)
  wait(PRODUCER_MUTEX) -> slots[tail] = message -> tail = next(tail)
  post(PRODUCER_MUTEX)
  post(FULL)

Shared memory:
  +--------+--------+-----------------------------------+
  |  head  |  tail  | slots[0] ... slots[capacity - 1] |
  +--------+--------+-----------------------------------+

Consumer:
  wait(FULL) -> message = slots[head] -> head = next(head)
  post(EMPTY)
```

Producers wait for `EMPTY` before taking `PRODUCER_MUTEX`, so they never hold the mutex while blocked for capacity. Only producers need the mutex: several producers share `tail`, while the single consumer exclusively updates `head`. Both indices wrap to zero at the configured capacity instead of growing indefinitely.

`EMPTY` and `FULL` provide bounded backpressure and transfer ownership of individual slots between producers and the consumer. A capacity of 1 reduces the protocol to mailbox-like behavior. Each producer sends one DONE message after its records; the consumer terminates only after receiving one valid, non-duplicate DONE from every producer.

The consumer waits for `FULL` with `semtimedop()` and a 100 ms timeout. On a timeout it checks child status with non-blocking `waitpid()`. If a producer failed, the semaphore set is removed before remaining children are reaped, waking producers blocked in semaphore operations instead of allowing an indefinite wait.

## Build and test

Requirements are a Linux environment with GCC, Make, and Python 3. The C targets use:

```text
-std=c11 -Wall -Wextra -Werror -pedantic
```

Available build targets:

```sh
make test     # Build and run all functional tests
make app      # Build the non-optimized development CLI
make release  # Build the benchmark CLI with -O2
make clean    # Remove the complete build/ directory
```

The optimized executable is:

```sh
./build/linux-concurrency-ipc-release
```

The release build uses `-O2` and `-pthread` without machine-specific optimization flags.

## CLI examples

Synchronization experiments:

```sh
./build/linux-concurrency-ipc sync process-unsafe 4 100000
./build/linux-concurrency-ipc sync threads-mutex 4 100000
./build/linux-concurrency-ipc sync process-sem 4 100000
```

IPC experiments:

```sh
./build/linux-concurrency-ipc ipc pipe 4 20000
./build/linux-concurrency-ipc ipc fifo 4 20000
./build/linux-concurrency-ipc ipc shm-mailbox 4 20000
./build/linux-concurrency-ipc ipc shm-ring 4 20000 8
```

Successful commands print exactly one machine-readable line of whitespace-separated `key=value` fields. Synchronization output includes expected and observed operations, lost updates, elapsed time, and operations per second. IPC output includes validation counters, elapsed time, and records per second; ring output also includes capacity.

## Correctness and stress testing

`make test` builds and runs focused assertion-based tests for the record, validator, I/O, timing, synchronization, and IPC layers.

The larger correctness suite runs with the optimized executable:

```sh
python3 scripts/stress.py
```

It executes each case once, sequentially, with a 120-second timeout per case. It excludes `process-unsafe` because that mode is intentionally racy. The synchronization workloads are:

- `threads-mutex`: 8 workers × 250,000 operations;
- `process-sem`: 8 workers × 25,000 operations.

Every IPC stress case uses 8 producers × 50,000 records, or 400,000 records total. Pipe, FIFO, and shared-memory mailbox are checked once each. The ring is checked at capacities 1, 2, 8, 64, 256, and 1024.

The runner verifies the returned family, mode, and workload metadata. Synchronized counters must be exact with zero lost updates. Every IPC case must receive all expected records, pass validation, and report zero missing, duplicate, corrupted, and out-of-range records. It stops immediately on a non-zero exit, malformed output, timeout, or correctness failure; it does not collect performance data.

## Benchmark methodology

The included dataset was generated with:

```sh
make release
python3 scripts/benchmark.py --repetitions 7
```

The benchmark runner uses the `-O2` release binary and executes cases sequentially. Synchronization cases use 4 workers × 100,000 operations. IPC cases use 4 producers × 20,000 records, and the ring is measured at capacities 1, 8, 64, 256, and 1024.

Each case is executed seven times for the included dataset. The runner parses the CLI's machine-readable output and applies correctness checks before accepting a measurement. It stores every accepted execution in [`results/benchmark_raw.csv`](results/benchmark_raw.csv) and calculates median elapsed time and throughput, plus minimum and maximum rate, in [`results/benchmark_summary.csv`](results/benchmark_summary.csv). The median is the primary statistic reported below.

These results were collected in Ubuntu running under WSL2. They describe this implementation and environment; they should not be generalized to all Linux systems or hardware.

## Final benchmark results

### Synchronization

| Mode | Median operations/sec | Correctness behavior |
|---|---:|---|
| `process-unsafe` | 939,271,407 | Intentionally racy; lost updates are nondeterministic |
| `threads-mutex` | 22,184,414 | Exact final count required |
| `process-sem` | 67,515 | Exact final count required |

The unsafe mode's high reported rate is not useful synchronized throughput. Its increments can overwrite one another, and throughput is calculated from the configured operation count. The included dataset has a median of zero lost updates, but that does not remove the data race or guarantee the same outcome in another run.

### Inter-process communication

| Mode | Capacity | Median records/sec |
|---|---:|---:|
| `pipe` | — | 230,411 |
| `fifo` | — | 228,811 |
| `shm-mailbox` | 1 | 29,179 |
| `shm-ring` | 1 | 21,388 |
| `shm-ring` | 8 | 43,972 |
| `shm-ring` | 64 | 36,351 |
| `shm-ring` | 256 | 34,498 |
| `shm-ring` | 1024 | 33,059 |

Values are rounded to the nearest whole operation or record per second. Exact values and per-run variation remain available in the CSV files.

## Interpretation

The pthread mutex counter was dramatically faster than the System V semaphore counter in this experiment. This is not a comparison of interchangeable primitives alone: the pthread case uses threads in one process, while the System V semaphore case synchronizes separate processes and invokes a different kernel IPC mechanism for every increment. The `process-sem` implementation also uses `SEM_UNDO`, so its measured cost includes the associated kernel bookkeeping.

Pipe and FIFO medians are close. Both also show substantial variation across the seven raw runs, so this dataset does not establish either transport as definitively faster.

The shared-memory results should not be summarized as “shared memory is slower than pipes.” The mailbox and ring perform System V semaphore operations around every transfer, so synchronization and ownership-transfer overhead are central parts of what these implementations measure.

Ring capacity 8 substantially outperformed capacity 1 for this workload, showing that buffering reduced producer backpressure. Increasing capacity beyond 8 did not improve throughput further in this dataset. That is an observation about this workload and environment, not evidence that capacity 8 is universally optimal.

## Project structure

```text
.
├── Makefile
├── README.md
├── include/
│   ├── io.h
│   ├── ipc.h
│   ├── record.h
│   ├── sync.h
│   ├── timing.h
│   └── validator.h
├── src/
│   ├── main.c
│   ├── common/
│   │   ├── io.c
│   │   ├── record.c
│   │   ├── timing.c
│   │   └── validator.c
│   ├── sync/
│   │   ├── process_unsafe.c
│   │   ├── processes_sem.c
│   │   └── threads_mutex.c
│   └── ipc/
│       ├── fifo.c
│       ├── pipe.c
│       ├── shm_mailbox.c
│       └── shm_ring.c
├── tests/
│   └── test_*.c
├── scripts/
│   ├── benchmark.py
│   └── stress.py
└── results/
    ├── benchmark_raw.csv
    └── benchmark_summary.csv
```

Generated binaries are placed under `build/` and are intentionally omitted from the tree above.

## What this project demonstrates

- Linux process creation, child reaping, and thread management
- Race conditions, read-modify-write hazards, and critical sections
- pthread mutex synchronization
- System V semaphore creation, operations, timeouts, and removal
- Anonymous pipes and named FIFOs with atomic record writes
- System V shared-memory attachment, detachment, and cleanup
- Multi-producer/single-consumer ownership-transfer protocols
- Capacity-1 mailboxes and bounded ring buffers with backpressure
- Failure-aware cleanup without busy waiting
- Deterministic integrity records and streaming correctness validation
- Strict C11 compilation, focused functional tests, stress testing, and reproducible benchmark summaries
