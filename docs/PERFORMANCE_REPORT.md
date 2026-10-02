# Performance report: producer-batched ring

A reproducible V3 comparison of the baseline System V ring (`shm-ring`) with the
producer-batched ring (`shm-ring-batch`). The protocol is described in
[Architecture](ARCHITECTURE.md#producer-batched-ring) and
[Reliability](RELIABILITY.md#batched-ring); general methodology is in
[Benchmarks](BENCHMARKS.md).

## Hypothesis

Amortizing producer semaphore reservation/publication across several records can
increase ring throughput when capacity permits useful batching. Tiny capacities
may gain little or regress because batching changes waiting and scheduling.
This is an implementation hypothesis, not a claim that shared memory universally
outperforms another IPC mechanism.

The [pre-optimization baseline](data/v3-ring-baseline.json) motivated batching:
capacity 2 constrained throughput relative to 64, with substantial repeat-to-repeat
spread. That earlier development dataset is explicitly marked dirty and is not
used for the final speedup calculation below.

## Method and reproducibility

- Source and build: clean commit `46e479a2de040afe15fb0e8029264b105bae3c85`.
- Real local environment: Intel Core i5-12450H, Linux `7.0.0-31-generic`,
  x86_64, 12 logical CPUs; affinity 0..11 unchanged. This is **not** the original
  V1 WSL2 dataset. GCC 13.3.0, strict C11 warnings, `-O2 -pthread`, no native flags.
- Both variants are in the same binary, SHA-256
  `40a325990282f2fc2e90d5c1165c71103f97050dd065da4d54df46538fd073e9`.
- Serial matrix: modes baseline/batch, producers 1/2, records per producer
  2,000/10,000, capacities 2/64. Maximum batch 8 gives effective batches 2/8.
- One warmup per case followed by four measured repetition blocks; cases are
  shuffled within each block with seed 2026. 80 executions: 16 warmups and 64
  accepted samples, 720,000 total records including warmups. Session wall time
  including launch/checkpoint overhead: 7.689 seconds.
- All 80 attempts passed record integrity/uniqueness/count validation, with no
  failed or cancelled attempts. No local tests/builds were run concurrently.
  Other machine activity, CPU frequency and thermal state were not controlled.

From a clean checkout of the measured commit (or `main`, whose later commits do not
change the engine sources or Makefile):

```sh
make release
.venv/bin/python -m ipc_lab.experiment --modes shm-ring,shm-ring-batch --workers 1,2 --amounts 2000,10000 --capacities 2,64 --repetitions 4 --warmups 1 --batch-size 8 --seed 2026 --perf
```

Use the [setup steps](USAGE.md#setup) first if `.venv` is absent. Scheduling and configuration are
reproducible; timings and generated run IDs are not expected to be identical.
The [raw schema-2 JSON](data/v3-comparison.json) retains every attempt, exact
commands, raw C fields, Python end-to-end wall times and provenance. The
[summary CSV](data/v3-comparison.csv) is derived from those measurements.

## Results

Median **worker-lifecycle** records/sec, four measured samples per cell:

| Producers | Records/producer | Capacity | Effective batch | Baseline/s | Batched/s | Ratio of medians |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2000 | 2 | 2 | 91,414.4 | 94,844.3 | 1.04× |
| 1 | 2000 | 64 | 8 | 193,361.9 | 354,312.1 | 1.83× |
| 1 | 10000 | 2 | 2 | 107,507.5 | 100,411.7 | 0.93× |
| 1 | 10000 | 64 | 8 | 219,372.0 | 420,151.1 | 1.92× |
| 2 | 2000 | 2 | 2 | 103,488.8 | 88,320.7 | 0.85× |
| 2 | 2000 | 64 | 8 | 132,962.0 | 361,908.2 | 2.72× |
| 2 | 10000 | 2 | 2 | 103,209.4 | 100,079.6 | 0.97× |
| 2 | 10000 | 64 | 8 | 151,194.7 | 465,360.1 | 3.08× |

Capacity 64 / batch 8 had higher medians in all four tested workloads, by about
1.83–3.08×. Capacity 2 / batch 2 was mixed, from about 0.85–1.04×. The small
positive difference at capacity 2 does **not** establish significance. Retaining
the baseline and configurable capacity/batch size is preferable to claiming a
universal win. The tables below show spread, not just selected medians.

## Timing and interpretation limits

The C interval starts immediately before worker creation and ends after consumer
processing and child reaping. It includes record generation, online validation,
scheduling, semaphore polling and cancellation checks. Initial allocation,
constant-time final validation summary and cleanup are outside it. Python wall
measurements include process launch and output drain. Neither is steady-state
instrumentation; no per-record latency was measured or inferred from throughput.

The baseline producer uses four successful semaphore operations per record; the
batched producer uses two per batch, while the consumer still acquires/releases
individual records. This explains the intended reduction in syscall work, but
hardware counters were unavailable, so the experiment does not establish a
hardware bottleneck or quantify cycles saved. Larger batches may increase waiting
or buffering delay; that latency tradeoff remains unmeasured.

Four observations per cell are a bounded laptop demonstration, not a significance
test. There is no affinity pinning, frequency control, sustained steady-state phase,
confidence interval or broad hardware survey. Validation and reliability overhead
remain enabled equally for both variants. Correctness CI has no performance threshold.

The [actual perf probe](data/v3-comparison-perf.json) returned exit 1 with unavailable
performance events under `perf_event_paranoid=4`. No kernel setting was changed,
no counter values were substituted, and ordinary measured timing continued.
Original V1 raw/summary datasets remain unchanged.

## Complete measured distributions and environment

### Run details

Run: `3b2d8a3f4ffc45bb8bf41a3622e2b3e1`; status: COMPLETE.
Seed: 2026; interleave: True; warmups per case: 1.

| Case | Workers | Items/worker | n | Correctness | Median/s | Min/s | Max/s | Sample SD/s |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| shm-ring / cap 2 / 1 × 2000 | 1 | 2000 | 4 | PASS | 91,414.4 | 74,852.1 | 107,196.1 | 13,259.1 |
| shm-ring / cap 64 / 1 × 2000 | 1 | 2000 | 4 | PASS | 193,361.9 | 150,076.6 | 207,518.8 | 25,683.0 |
| shm-ring / cap 2 / 1 × 10000 | 1 | 10000 | 4 | PASS | 107,507.5 | 106,468.1 | 108,909.0 | 1,114.6 |
| shm-ring / cap 64 / 1 × 10000 | 1 | 10000 | 4 | PASS | 219,372.0 | 209,011.5 | 231,022.9 | 9,027.8 |
| shm-ring / cap 2 / 2 × 2000 | 2 | 2000 | 4 | PASS | 103,488.8 | 88,523.3 | 111,395.2 | 9,670.3 |
| shm-ring / cap 64 / 2 × 2000 | 2 | 2000 | 4 | PASS | 132,962.0 | 130,317.9 | 148,571.9 | 8,518.0 |
| shm-ring / cap 2 / 2 × 10000 | 2 | 10000 | 4 | PASS | 103,209.4 | 97,539.1 | 124,408.3 | 11,906.8 |
| shm-ring / cap 64 / 2 × 10000 | 2 | 10000 | 4 | PASS | 151,194.7 | 128,167.2 | 154,326.7 | 12,149.3 |
| shm-ring-batch / cap 2 / batch 2 / 1 × 2000 | 1 | 2000 | 4 | PASS | 94,844.3 | 85,015.3 | 98,630.9 | 6,128.2 |
| shm-ring-batch / cap 64 / batch 8 / 1 × 2000 | 1 | 2000 | 4 | PASS | 354,312.1 | 271,497.1 | 391,770.7 | 54,915.0 |
| shm-ring-batch / cap 2 / batch 2 / 1 × 10000 | 1 | 10000 | 4 | PASS | 100,411.7 | 92,483.7 | 102,728.9 | 4,500.9 |
| shm-ring-batch / cap 64 / batch 8 / 1 × 10000 | 1 | 10000 | 4 | PASS | 420,151.1 | 396,452.3 | 430,100.3 | 15,272.7 |
| shm-ring-batch / cap 2 / batch 2 / 2 × 2000 | 2 | 2000 | 4 | PASS | 88,320.7 | 70,466.9 | 93,536.2 | 10,226.9 |
| shm-ring-batch / cap 64 / batch 8 / 2 × 2000 | 2 | 2000 | 4 | PASS | 361,908.2 | 350,157.0 | 449,160.3 | 45,931.3 |
| shm-ring-batch / cap 2 / batch 2 / 2 × 10000 | 2 | 10000 | 4 | PASS | 100,079.6 | 89,411.3 | 102,789.7 | 5,926.6 |
| shm-ring-batch / cap 64 / batch 8 / 2 × 10000 | 2 | 10000 | 4 | PASS | 465,360.1 | 453,357.1 | 495,379.1 | 18,311.3 |

Rates use the C worker-lifecycle interval, including generation, online validation and reaping.
Raw JSON retains exact commands, build/source provenance, output and Python end-to-end wall times.
Warmups and invalid measurements are excluded. No steady-state or latency measurement was made.
Spread is descriptive; small median differences do not establish significance.

```json
{
  "system": "Linux",
  "release": "7.0.0-31-generic",
  "machine": "x86_64",
  "cpu_count": "12",
  "python": "3.12.3",
  "engine": "linux-concurrency-ipc-release",
  "engine_sha256": "40a325990282f2fc2e90d5c1165c71103f97050dd065da4d54df46538fd073e9",
  "source_commit": "46e479a2de040afe15fb0e8029264b105bae3c85",
  "source_dirty": "false",
  "cpu_model": "12th Gen Intel(R) Core(TM) i5-12450H",
  "cpu_affinity": "0,1,2,3,4,5,6,7,8,9,10,11",
  "compiler": "gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0",
  "compiler_flags": "-Iinclude -std=c11 -Wall -Wextra -Werror -pedantic -O2 -pthread",
  "build_commit": "46e479a2de040afe15fb0e8029264b105bae3c85",
  "build_dirty": "false"
}
```
