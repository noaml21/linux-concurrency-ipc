# Usage

This guide covers the interactive lab, headless reproducible experiments and the
C engine CLI. For a guided tour, see the [five-minute demo](DEMO.md).

## Setup

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
not install dependencies or build binaries automatically. An interactive
terminal is required; 100×32 or larger is comfortable, 80×24 is supported, and a
60×20 keyboard smoke test covers smaller terminals. Scroll panels to reveal
additional controls and details; tables also scroll horizontally.

The C engine and the V1 scripts do not need Textual; only `make` and Python 3
are required for those.

## Interactive workflow

![Configure tab of the lab](images/lab-configuration.svg)

1. **Configure:** choose IPC or synchronization, then select mechanisms with
   Space. Set workers/producers, items **per worker/producer**, repetitions, and
   ring capacity. The default runs the four IPC mechanisms with 2 producers ×
   2,000 records, three times each. The batched ring (`shm-ring-batch`) is
   opt-in. Validation explains invalid or excessive workloads.
2. **Sweep:** enable “Sweep shm-ring capacity” to select the ring and replace its
   single capacity with `1, 2, 8, 64, 256, 1024`. You can edit the
   comma-separated capacities (at most eight distinct values). Other selected
   modes run once per repetition at the same workload, without the capacity
   dimension.
3. **Live:** Run or Ctrl+R starts sequential background execution. The app shows
   the current mechanism/repetition, elapsed wall time, actual completed
   executions, failures and the last correctness result. Progress advances only
   when the engine returns; it is not a record-level estimate.
4. **Results:** select a row to see validation counters, expected and observed
   counts, accepted-sample sparkline, and the original engine output. The table
   shows median/min/max throughput and accepted/planned sample count (`n`).
   Export summary CSV writes a separate lab CSV under `results/lab/exports/`.
5. **History:** select a saved run and Open it. To compare, Pin baseline, select
   a different run, then Compare. Both must be complete without failures, with
   identical configuration, recorded system metadata, and engine digest.

Configure also exposes warmups (0..3), a seed, randomized/interleaved repetition
blocks, the per-execution deadline, the maximum batch size, and optional
worker-count and item-count matrices.

### Keys

| Key | Action |
|---|---|
| Tab / Shift+Tab | Move focus |
| Arrows | Move through tables and selections |
| Space | Toggle a checkbox or selected mechanism |
| Ctrl+R | Run |
| Ctrl+X | Request cancellation |
| Ctrl+Q or Ctrl+C | Safe quit (drains and saves history) |
| Ctrl+P | Command palette |

### Cancellation and deadlines

**Cancel asks the active C owner to stop, reap children and remove its
resources.** The engine polls cancellation/deadlines at blocking boundaries and
escalates stalled owned children from SIGTERM to SIGKILL after 200 ms. Quit
drains and saves history. Use trailing `--deadline-ms 1..120000` in the CLI, or
Deadline ms in Configure. Default deadline is 30 seconds; very short cases may
finish before cancellation.

This is cooperative bounded shutdown under normal Linux scheduling, not a
real-time promise. Uninterruptible kernel sleep, owner SIGKILL and machine
failure cannot have guaranteed cleanup. The UI has an emergency watchdog, which
reports failure and explicitly cannot promise cleanup of an unresponsive owner.
See [Reliability](RELIABILITY.md) for the full design.

### Workload limits

UI limits: 1–32 workers/producers, 1–100,000 items each, at most 200,000 items
per execution, 1–15 repetitions, capacities 1–32,767, at most 90 executions and
5,000,000 configured items including warmups per experiment. The lab stops
scheduling after 600 seconds; the current execution still gets its deadline and
cleanup grace. The engine itself accepts at most 64 workers.

## Headless reproducible experiments

`ipc_lab.experiment` runs bounded matrices through the same runner and history
as the UI, without importing Textual:

```sh
# Short demo, same C engine and history as the UI
.venv/bin/python -m ipc_lab.experiment --modes shm-ring,shm-ring-batch --workers 1,2 --amounts 100,2000 --capacities 2,64 --repetitions 3 --warmups 1 --batch-size 8 --seed 2026
# Longer bounded ring study; defaults stay within 90 executions
.venv/bin/python -m ipc_lab.experiment --preset research --perf
```

JSON, summary CSV and a Markdown distribution report go under `results/lab/`.
The headless CLI interleaves repetition blocks with the recorded seed; the UI
keeps ordered V2 scheduling unless the checkbox is enabled. The optional
separate `--perf` probe records actual `perf stat` output or its unavailability
and never changes kernel settings. Research presets remain limited laptop
experiments, not publication-quality evidence; explicit arguments exceeding
bounds are rejected.

## C engine CLI

Build with `make release` (optimized, `build/linux-concurrency-ipc-release`) or
`make app` (development build, `build/linux-concurrency-ipc`). Run `--help` for
the full usage text.

Synchronization experiments (`<workers> <operations_per_worker>`):

```sh
./build/linux-concurrency-ipc-release sync process-unsafe 4 100000
./build/linux-concurrency-ipc-release sync threads-mutex 4 100000
./build/linux-concurrency-ipc-release sync process-sem 4 100000
```

IPC experiments (`<producers> <records_per_producer> [capacity] [batch_size]`):

```sh
./build/linux-concurrency-ipc-release ipc pipe 4 20000
./build/linux-concurrency-ipc-release ipc fifo 4 20000
./build/linux-concurrency-ipc-release ipc shm-mailbox 4 20000
./build/linux-concurrency-ipc-release ipc shm-ring 4 20000 8
./build/linux-concurrency-ipc-release ipc shm-ring-batch 4 20000 64 8 --deadline-ms 5000
```

Successful commands print exactly one machine-readable line of
whitespace-separated `key=value` fields, for example:

```text
family=ipc mode=shm-ring producers=4 records_per_producer=20000 capacity=8 expected=80000 received=80000 missing=0 duplicates=0 corrupted=0 out_of_range=0 validation_pass=1 elapsed_seconds=0.685255 records_per_second=116744.877757
```

Synchronization output includes expected and observed operations, lost updates,
elapsed time, and operations per second. IPC output includes validation counters,
elapsed time, and records per second; ring output also includes capacity; batch
mode additionally includes `batch_size`. A validation failure returns nonzero.
Batch size must not exceed capacity in the C CLI. In the lab, Max batch is
clamped to each case capacity and recorded explicitly.

## Original V1 benchmark suite

`scripts/benchmark.py` runs the fixed V1 case list against the release binary
and writes raw and summary CSVs. Its default `--output-dir` is `results/`, which
**overwrites the committed V1 dataset**; point it elsewhere for local runs:

```sh
python3 scripts/benchmark.py --repetitions 3 --output-dir results/lab/v1-local
```

See [Benchmarks](BENCHMARKS.md#original-v1-dataset-wsl2) for the dataset and how
it was produced.
