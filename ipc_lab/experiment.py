"""Bounded reproducible headless experiments using the same runner/history as the UI."""
import argparse
import asyncio
import json
from pathlib import Path
import shutil
import signal
import statistics
import subprocess

from .models import Config
from .runner import run_experiment
from .storage import History, atomic_write

ROOT = Path(__file__).resolve().parent.parent


def perf_probe(binary: Path, case, directory: Path) -> dict:
    """An optional separate investigation, never part of throughput samples."""
    perf = shutil.which("perf")
    if not perf:
        return {"available": False, "reason": "perf executable unavailable"}
    command = [perf, "stat", "-x,", "-e", "task-clock,cycles,instructions,context-switches",
               "--", *case.command(binary), "--deadline-ms", "5000"]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=10)
        return {"available": result.returncode == 0, "command": command,
                "returncode": result.returncode, "stdout": result.stdout[:16000],
                "stderr": result.stderr[:16000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"available": False, "reason": str(error)}


def report(run) -> str:
    lines = ["# Local IPC experiment", "", f"Run: `{run.run_id}`; status: {run.status}.",
             f"Seed: {run.config.seed}; interleave: {run.config.interleave}; warmups per case: {run.config.warmups}.",
             "", "| Case | Workers | Items/worker | n | Correctness | Median/s | Min/s | Max/s | Sample SD/s |",
             "|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    for summary in run.summaries():
        rates = [a.measurement.rate for a in run.attempts if a.case == summary.case
                 and a.repetition > 0 and a.correctness in ("PASS", "RACY")]
        def fmt(value):
            return "—" if value is None else f"{value:,.1f}"
        lines.append(f"| {summary.case.name} | {summary.case.workers} | {summary.case.amount} | "
                     f"{summary.accepted} | {summary.correctness} | {fmt(summary.median_rate)} | "
                     f"{fmt(summary.min_rate)} | {fmt(summary.max_rate)} | "
                     f"{fmt(statistics.stdev(rates) if len(rates) > 1 else None)} |")
    lines += ["", "Rates use the C worker-lifecycle interval, including generation, online validation and reaping.",
              "Raw JSON retains exact commands, build/source provenance, output and Python end-to-end wall times.",
              "Warmups and invalid measurements are excluded. No steady-state or latency measurement was made.",
              "Spread is descriptive; small median differences do not establish significance.", "",
              "```json", json.dumps(run.system, indent=2), "```", ""]
    return "\n".join(lines)


async def main_async(args) -> int:
    config = Config(modes=tuple(args.modes.split(",")),
                    worker_matrix=tuple(map(int, args.workers.split(","))),
                    amount_matrix=tuple(map(int, args.amounts.split(","))),
                    sweep=tuple(map(int, args.capacities.split(","))),
                    repetitions=args.repetitions, warmups=args.warmups,
                    seed=args.seed, interleave=True, deadline_ms=args.deadline_ms)
    binary = ROOT / "build/linux-concurrency-ipc-release"
    history = History(ROOT / "results/lab")
    cancel = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, cancel.set)
    run = await run_experiment(config, binary, cancel, checkpoint=history.save)
    path = history.save(run)
    history.export_csv(run)
    atomic_write(path.with_suffix(".md"), report(run))
    if args.perf:
        probe = await asyncio.to_thread(perf_probe, binary, config.cases()[0], history.directory)
        atomic_write(history.directory / "investigations" / f"{run.run_id}.json", json.dumps(probe, indent=2) + "\n")
        print("perf:", "available" if probe["available"] else "unavailable (see recorded diagnostics)")
    print(f"{run.status}: {path}")
    return 0 if run.status == "COMPLETE" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=("demo", "research"), default="demo")
    parser.add_argument("--modes", default="shm-ring")
    parser.add_argument("--workers", default="1,2")
    parser.add_argument("--amounts", default="100,2000")
    parser.add_argument("--capacities", default="2,64")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--deadline-ms", type=int, default=5000)
    parser.add_argument("--perf", action="store_true")
    args = parser.parse_args()
    if args.preset == "research":
        # Still bounded: 56 executions with defaults, not an unbounded laptop sweep.
        args.amounts = "2000,10000"
        args.repetitions = 6
    try:
        return asyncio.run(main_async(args))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
