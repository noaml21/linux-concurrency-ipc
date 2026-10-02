# Documentation

| I want to… | Read |
|---|---|
| Install and run the lab, headless experiments or the C CLI | [Usage](USAGE.md) |
| Take a guided five-minute tour | [Demo](DEMO.md) |
| Understand the engine, record validation and the ring protocol | [Architecture](ARCHITECTURE.md) |
| Understand cancellation, cleanup, invariants and fault coverage | [Reliability](RELIABILITY.md) |
| Read numbers correctly and see the V1 dataset | [Benchmarks and methodology](BENCHMARKS.md) |
| See the measured batched-ring comparison | [Performance report](PERFORMANCE_REPORT.md) |
| Know what is tested and how CI runs | [Testing and verification](TESTING.md) |
| Study the implementation and prepare to explain it | [Study guide](STUDY_GUIDE.md) |

## Data

[`data/`](data/) holds the committed evidence behind the performance report:

| File | Contents |
|---|---|
| [`v3-comparison.json`](data/v3-comparison.json) | Raw schema-2 run: every attempt, command, engine output and provenance |
| [`v3-comparison.csv`](data/v3-comparison.csv) | Summary CSV derived from that run |
| [`v3-comparison-perf.json`](data/v3-comparison-perf.json) | `perf stat` probe for that run (events unavailable) |
| [`v3-ring-baseline.json`](data/v3-ring-baseline.json) | Pre-optimization development baseline (dirty build, not used for speedups) |
| [`v3-perf-probe.json`](data/v3-perf-probe.json) | `perf stat` probe from the development baseline (events unavailable) |

The original V1 dataset lives in [`../results/`](../results/).

## Project history

The project grew in three stages: a C benchmark engine (V1), the interactive
Textual lab (V2), and reliability, reproducibility and the batched ring (V3).
The V2 plan, build log and walkthrough are kept for provenance in
[`history/`](history/).
