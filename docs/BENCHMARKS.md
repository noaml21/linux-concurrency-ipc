# Benchmarks and methodology

How measurements are taken, how to read them, and what the committed datasets
show. The batched-ring study has its own [performance report](PERFORMANCE_REPORT.md).

## What is timed

Engine `elapsed_seconds` is the **worker-lifecycle interval**: it begins
immediately before worker creation and ends after consumption and child
reaping/joining. It includes worker creation, record generation, transport,
online validation, scheduling, polling and reaping. Resource allocation, the
final constant-time validator summary and resource destruction are outside that
interval. Python also records end-to-end process wall time, which includes
process launch and output drain. Neither is steady-state throughput or
per-record latency, and no per-record latency is instrumented.

Elapsed time is measured with `clock_gettime(CLOCK_MONOTONIC)`. V3 cancellation
checks have measurable cost, so comparisons must use the same build and
validation settings.

## Interpreting results

- IPC rates are records/sec. Correctness requires every expected record exactly
  once, no corruption, and no out-of-range records. Counter details and CSV
  counters are **sums across parsed repetitions**, including incorrect ones.
- Synchronized counters require observed = expected and zero lost updates.
  `process-unsafe` is always labeled **RACY**, even if no loss happens in a run.
  Its reported rate is **attempted operations/sec**, not useful synchronized
  throughput; it is excluded from the common relative-performance bar scale.
- Invalid output and nonzero exits are errors. Parsed correctness failures
  remain visible but are excluded from rate statistics. A cancelled experiment
  retains completed samples, and unexecuted cases display NOT RUN. A failing
  case can still have accepted samples; always inspect its state and sample count.
- Median bars are relative to accepted medians in that run. Sparklines show
  accepted repetitions in execution order. Min/max describe spread, not a
  confidence interval. Tiny demo workloads emphasize startup/scheduling overhead.

## Experiment protocol

- Runs are sequential; nothing is measured concurrently.
- Optional worker/item matrices, 0..3 warmups, a seed and randomized/interleaved
  repetition blocks can be configured. Interleaving shuffles each repetition
  block with a recorded seed; all warmup blocks precede measured blocks. The
  headless experiment CLI defaults to interleaving; the UI preserves ordered V2
  defaults.
- Warmups remain in raw history but never enter performance statistics.
- CPU affinity is recorded, not changed. CPU frequency, system load and
  scheduling remain uncontrolled.
- Every run records the exact command, raw output, engine digest, source and
  build provenance, compiler flags and CPU information
  (see [Architecture → Stored data](ARCHITECTURE.md#stored-data-and-history)).

Results are descriptive measurements of this implementation on a specific
machine. They are not significance tests and should not be generalized to all
Linux systems or hardware.

## V3 batched-ring study

A seeded, interleaved 80-execution matrix on a clean build compared the baseline
ring with the producer-batched ring. Capacity 64 with an effective batch of 8 had
higher median throughput in all four tested workloads (about 1.83–3.08×);
capacity 2 with batch 2 was mixed (about 0.85–1.04×). Hardware counters were
unavailable under the kernel's `perf_event_paranoid` policy, so no
hardware-bottleneck claim is made. Full method, distributions, raw data and
environment: [performance report](PERFORMANCE_REPORT.md).

## Original V1 dataset (WSL2)

These results predate the V2 lab and V3 reliability work and are preserved
unchanged.

### Method

The included dataset was generated with:

```sh
make release
python3 scripts/benchmark.py --repetitions 7
```

The benchmark runner uses the `-O2` release binary and executes cases
sequentially. Synchronization cases use 4 workers × 100,000 operations. IPC cases
use 4 producers × 20,000 records, and the ring is measured at capacities 1, 8,
64, 256, and 1024.

Each case is executed seven times for the included dataset. The runner parses the
CLI's machine-readable output and applies correctness checks before accepting a
measurement. It stores every accepted execution in
[`results/benchmark_raw.csv`](../results/benchmark_raw.csv) and calculates median
elapsed time and throughput, plus minimum and maximum rate, in
[`results/benchmark_summary.csv`](../results/benchmark_summary.csv). The median is
the primary statistic reported below.

These results were collected in Ubuntu running under WSL2. They describe this
implementation and environment; they should not be generalized to all Linux
systems or hardware.

### Synchronization

| Mode | Median operations/sec | Correctness behavior |
|---|---:|---|
| `process-unsafe` | 939,271,407 | Intentionally racy; lost updates are nondeterministic |
| `threads-mutex` | 22,184,414 | Exact final count required |
| `process-sem` | 67,515 | Exact final count required |

The unsafe mode's high reported rate is not useful synchronized throughput. Its
increments can overwrite one another, and throughput is calculated from the
configured operation count. The included dataset has a median of zero lost
updates, but that does not remove the data race or guarantee the same outcome in
another run.

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

Values are rounded to the nearest whole operation or record per second. Exact
values and per-run variation remain available in the CSV files.

### Interpretation

The pthread mutex counter was dramatically faster than the System V semaphore
counter in this experiment. This is not a comparison of interchangeable
primitives alone: the pthread case uses threads in one process, while the System
V semaphore case synchronizes separate processes and invokes a different kernel
IPC mechanism for every increment. The `process-sem` implementation also uses
`SEM_UNDO`, so its measured cost includes the associated kernel bookkeeping.

Pipe and FIFO medians are close. Both also show substantial variation across the
seven raw runs, so this dataset does not establish either transport as
definitively faster.

The shared-memory results should not be summarized as “shared memory is slower
than pipes.” The mailbox and ring perform System V semaphore operations around
every transfer, so synchronization and ownership-transfer overhead are central
parts of what these implementations measure.

Ring capacity 8 substantially outperformed capacity 1 for this workload, showing
that buffering reduced producer backpressure. Increasing capacity beyond 8 did
not improve throughput further in this dataset. That is an observation about this
workload and environment, not evidence that capacity 8 is universally optimal.
