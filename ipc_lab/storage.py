"""Versioned, validated JSON history and a separate V2 summary CSV format."""

import csv
import io
import json
import math
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .models import Case, Config
from .records import Attempt, Run


SCHEMA_VERSION = 2
MAX_HISTORY_BYTES = 2_000_000


def serialize(run: Run) -> str:
    return json.dumps({"schema_version": SCHEMA_VERSION, **asdict(run)}, indent=2, allow_nan=False) + "\n"


def deserialize(text: str) -> Run:
    try:
        data = json.loads(text)
        required = {"schema_version", "config", "system", "run_id", "started", "finished", "cancelled", "attempts"}
        if type(data) is not dict or set(data) != required:
            raise ValueError("Missing or unexpected history fields")
        version = data.pop("schema_version")
        if type(version) is not int or version not in (1, SCHEMA_VERSION):
            raise ValueError("Unsupported history schema")
        raw_config = data.pop("config")
        raw_config["modes"] = tuple(raw_config["modes"])
        raw_config["sweep"] = tuple(raw_config["sweep"])
        for key in ("worker_matrix", "amount_matrix"):
            if key in raw_config:
                raw_config[key] = tuple(raw_config[key])
        if version == 1:
            raw_config["interleave"] = False
        config = Config(**raw_config)
        raw_attempts = data.pop("attempts")
        if not isinstance(raw_attempts, list) or len(raw_attempts) > config.total:
            raise ValueError("Invalid history execution count")
        run = Run(config=config, attempts=[], **data)
        if not isinstance(run.run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run.run_id):
            raise ValueError("Invalid run ID")
        for timestamp in (run.started, run.finished):
            if timestamp is not None and datetime.fromisoformat(timestamp).tzinfo is None:
                raise ValueError("History timestamps must include a timezone")
        if not isinstance(run.started, str) or type(run.cancelled) is not bool:
            raise ValueError("Invalid history run metadata")
        if not isinstance(run.system, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in run.system.items()):
            raise ValueError("Invalid system metadata")
        required_system = {"system", "release", "machine", "cpu_count", "python", "engine", "engine_sha256"}
        allowed_system = required_system | {"source_commit", "source_dirty", "cpu_model", "cpu_affinity",
                                            "compiler", "compiler_flags", "build_commit", "build_dirty"}
        if not required_system <= set(run.system) <= allowed_system or not re.fullmatch(r"[a-f0-9]{64}", run.system["engine_sha256"]):
            raise ValueError("Missing or invalid system/engine metadata")
        schedule = config.schedule()
        for index, raw in enumerate(raw_attempts):
            required_attempt = {"case", "repetition", "stdout", "stderr", "returncode", "launch_error"}
            if version == 2:
                required_attempt |= {"command", "wall_seconds"}
            if set(raw) != required_attempt:
                raise ValueError("Missing or unexpected execution fields")
            if "command" in raw:
                if not isinstance(raw["command"], list) or not all(isinstance(v, str) for v in raw["command"]):
                    raise ValueError("Invalid exact command")
                raw["command"] = tuple(raw["command"])
            attempt = Attempt(case=Case(**raw.pop("case")), **raw)
            if attempt.wall_seconds is not None and (type(attempt.wall_seconds) not in (int, float)
                    or not math.isfinite(attempt.wall_seconds) or attempt.wall_seconds < 0):
                raise ValueError("Invalid wall time")
            if type(attempt.repetition) is not int or (attempt.case, attempt.repetition) != schedule[index]:
                raise ValueError("History executions do not match the configured schedule")
            if not all(isinstance(value, str) for value in (attempt.stdout, attempt.stderr, attempt.launch_error)):
                raise ValueError("History output must be text")
            if attempt.returncode is not None and type(attempt.returncode) is not int:
                raise ValueError("Invalid engine exit code")
            if (attempt.returncode is None) != bool(attempt.launch_error):
                raise ValueError("Invalid launch failure metadata")
            run.attempts.append(attempt)
        if run.finished and not run.cancelled and len(run.attempts) != config.total:
            raise ValueError("Finished history is missing executions")
        return run
    except (KeyError, TypeError, AttributeError, OverflowError, ValueError) as error:
        raise ValueError(f"Invalid lab history: {error}") from error


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


class History:
    def __init__(self, directory: Path):
        self.directory = directory

    def save(self, run: Run) -> Path:
        text = serialize(run)
        deserialize(text)  # Apply the same schema checks when writing and reading.
        path = self.directory / f"{run.run_id}.json"
        atomic_write(path, text)
        return path

    def load(self, path: Path) -> Run:
        if path.resolve().parent != self.directory.resolve():
            raise ValueError("History path must belong to the lab history directory")
        if path.stat().st_size > MAX_HISTORY_BYTES:
            raise ValueError("History file is too large")
        return deserialize(path.read_text(encoding="utf-8"))

    def list_runs(self) -> tuple[list[Run], list[str]]:
        runs, errors = [], []
        for path in sorted(self.directory.glob("*.json")):
            try:
                runs.append(self.load(path))
            except (OSError, ValueError) as error:
                errors.append(f"{path.name}: {error}")
        return sorted(runs, key=lambda run: run.started, reverse=True), errors

    def export_csv(self, run: Run) -> Path:
        # Validate IDs before using them in filenames, including imported history.
        deserialize(serialize(run))
        output = io.StringIO(newline="")
        columns = ["run_id", "started", "status", "family", "mode", "workers_or_producers",
                   "items_per_worker_or_producer", "capacity", "batch_size", "planned_repetitions",
                   "accepted_samples", "failures", "correctness", "rate_unit",
                   "median_rate", "min_rate", "max_rate", "expected_per_execution",
                   "observed_min", "observed_max", "missing_total", "duplicates_total",
                   "corrupted_total", "out_of_range_total", "lost_updates_total"]
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for summary in run.summaries():
            case = summary.case
            row = dict(run_id=run.run_id, started=run.started, status=run.status,
                       family=case.family, mode=case.mode, workers_or_producers=case.workers,
                       items_per_worker_or_producer=case.amount, capacity=case.capacity, batch_size=case.batch_size,
                       planned_repetitions=run.config.repetitions, accepted_samples=summary.accepted,
                       failures=summary.failures, correctness=summary.correctness,
                       rate_unit="records/sec" if case.family == "ipc" else ("attempted operations/sec" if case.mode == "process-unsafe" else "operations/sec"),
                       median_rate=summary.median_rate, min_rate=summary.min_rate,
                       max_rate=summary.max_rate, expected_per_execution=case.workers * case.amount,
                       observed_min=summary.observed_min, observed_max=summary.observed_max)
            row.update({key + "_total": value for key, value in summary.counters.items()})
            writer.writerow(row)
        path = self.directory / "exports" / f"{run.run_id}.csv"
        atomic_write(path, output.getvalue())
        return path


def compare_runs(baseline: Run, current: Run) -> list[tuple[str, float, float, float | None]]:
    if baseline.status != "COMPLETE" or current.status != "COMPLETE":
        raise ValueError("Comparison requires two complete runs without failures")
    if baseline.config != current.config or baseline.system != current.system:
        raise ValueError("Comparison requires identical configuration, engine and system metadata")
    comparisons = []
    for before, after in zip(baseline.summaries(), current.summaries()):
        if before.median_rate is None or after.median_rate is None:
            raise ValueError("Comparison requires measured samples")
        delta = (after.median_rate / before.median_rate - 1) * 100 if before.median_rate else None
        comparisons.append((before.case.name, before.median_rate, after.median_rate, delta))
    return comparisons
