# Results

| Path | Contents |
|---|---|
| `benchmark_raw.csv` | Original V1 dataset: every accepted execution (WSL2, 7 repetitions per case) |
| `benchmark_summary.csv` | Median elapsed time and median/min/max rate per V1 case |
| `lab/` | Local lab history, exports and reports — Git-ignored, created on first run |

Method, tables and interpretation for the V1 dataset are in
[Benchmarks](../docs/BENCHMARKS.md#original-v1-dataset-wsl2).

`scripts/benchmark.py` writes to this directory by default and would overwrite
the committed dataset. For local runs, pass `--output-dir results/lab/<name>`.
