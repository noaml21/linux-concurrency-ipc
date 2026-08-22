#!/usr/bin/env python3

import argparse
import csv
import math
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


RAW_COLUMNS = [
    "case",
    "repetition",
    "family",
    "mode",
    "workers",
    "operations_per_worker",
    "producers",
    "records_per_producer",
    "capacity",
    "expected",
    "observed",
    "received",
    "lost_updates",
    "missing",
    "duplicates",
    "corrupted",
    "out_of_range",
    "validation_pass",
    "elapsed_seconds",
    "rate",
]

SUMMARY_COLUMNS = [
    "case",
    "family",
    "mode",
    "workers",
    "operations_per_worker",
    "producers",
    "records_per_producer",
    "capacity",
    "repetitions",
    "median_elapsed_seconds",
    "median_rate",
    "min_rate",
    "max_rate",
    "median_lost_updates",
]


class BenchmarkError(Exception):
    pass


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    family: str
    mode: str
    workers: Optional[int] = None
    operations_per_worker: Optional[int] = None
    producers: Optional[int] = None
    records_per_producer: Optional[int] = None
    capacity: Optional[int] = None

    def command(self, binary: Path) -> List[str]:
        if self.family == "sync":
            return [
                str(binary),
                "sync",
                self.mode,
                str(self.workers),
                str(self.operations_per_worker),
            ]

        command = [
            str(binary),
            "ipc",
            self.mode,
            str(self.producers),
            str(self.records_per_producer),
        ]
        if self.capacity is not None:
            command.append(str(self.capacity))
        return command


def positive_integer(text: str) -> int:
    try:
        value = int(text, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error

    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def benchmark_cases() -> List[BenchmarkCase]:
    cases = [
        BenchmarkCase("sync-process-unsafe", "sync", "process-unsafe", 4, 100000),
        BenchmarkCase("sync-threads-mutex", "sync", "threads-mutex", 4, 100000),
        BenchmarkCase("sync-process-sem", "sync", "process-sem", 4, 100000),
        BenchmarkCase(
            "ipc-pipe",
            "ipc",
            "pipe",
            producers=4,
            records_per_producer=20000,
        ),
        BenchmarkCase(
            "ipc-fifo",
            "ipc",
            "fifo",
            producers=4,
            records_per_producer=20000,
        ),
        BenchmarkCase(
            "ipc-shm-mailbox",
            "ipc",
            "shm-mailbox",
            producers=4,
            records_per_producer=20000,
        ),
    ]

    for capacity in (1, 8, 64, 256, 1024):
        cases.append(
            BenchmarkCase(
                f"ipc-shm-ring-cap{capacity}",
                "ipc",
                "shm-ring",
                producers=4,
                records_per_producer=20000,
                capacity=capacity,
            )
        )

    return cases


def parse_result_line(stdout: str) -> Dict[str, str]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise BenchmarkError(
            f"expected exactly one non-empty stdout line, received {len(lines)}"
        )

    fields: Dict[str, str] = {}
    for token in lines[0].split():
        key, separator, value = token.partition("=")
        if (
            token.count("=") != 1
            or separator != "="
            or not key
            or not value
            or key in fields
        ):
            raise BenchmarkError(f"malformed result field: {token!r}")
        fields[key] = value

    return fields


def required_integer(fields: Dict[str, str], name: str) -> int:
    if name not in fields:
        raise BenchmarkError(f"missing result field: {name}")

    try:
        value = int(fields[name], 10)
    except ValueError as error:
        raise BenchmarkError(f"result field {name} is not an integer") from error

    if value < 0:
        raise BenchmarkError(f"result field {name} must not be negative")
    return value


def required_nonnegative_float(fields: Dict[str, str], name: str) -> float:
    if name not in fields:
        raise BenchmarkError(f"missing result field: {name}")

    try:
        value = float(fields[name])
    except ValueError as error:
        raise BenchmarkError(f"result field {name} is not numeric") from error

    if not math.isfinite(value) or value < 0.0:
        raise BenchmarkError(f"result field {name} must be finite and non-negative")
    return value


def require_metadata(case: BenchmarkCase, fields: Dict[str, str]) -> None:
    if fields.get("family") != case.family:
        raise BenchmarkError("result family does not match the requested case")
    if fields.get("mode") != case.mode:
        raise BenchmarkError("result mode does not match the requested case")

    if case.family == "sync":
        if required_integer(fields, "workers") != case.workers:
            raise BenchmarkError("result workers does not match the requested case")
        if (
            required_integer(fields, "operations_per_worker")
            != case.operations_per_worker
        ):
            raise BenchmarkError(
                "result operations_per_worker does not match the requested case"
            )
    else:
        if required_integer(fields, "producers") != case.producers:
            raise BenchmarkError("result producers does not match the requested case")
        if (
            required_integer(fields, "records_per_producer")
            != case.records_per_producer
        ):
            raise BenchmarkError(
                "result records_per_producer does not match the requested case"
            )
        if case.capacity is not None:
            if required_integer(fields, "capacity") != case.capacity:
                raise BenchmarkError("result capacity does not match the requested case")


def validate_sync(case: BenchmarkCase, fields: Dict[str, str]) -> None:
    expected = required_integer(fields, "expected")
    observed = required_integer(fields, "observed")
    lost_updates = required_integer(fields, "lost_updates")

    if expected != case.workers * case.operations_per_worker:
        raise BenchmarkError("sync expected count does not match the workload")
    if observed > expected:
        raise BenchmarkError("sync observed count exceeds expected count")
    if lost_updates != expected - observed:
        raise BenchmarkError("sync lost_updates is inconsistent")

    if case.mode in ("threads-mutex", "process-sem"):
        if observed != expected or lost_updates != 0:
            raise BenchmarkError(f"synchronized mode {case.mode} lost updates")


def validate_ipc(case: BenchmarkCase, fields: Dict[str, str]) -> None:
    expected = required_integer(fields, "expected")
    received = required_integer(fields, "received")

    if expected != case.producers * case.records_per_producer:
        raise BenchmarkError("IPC expected count does not match the workload")
    if required_integer(fields, "validation_pass") != 1:
        raise BenchmarkError("IPC validation_pass is not 1")
    if received != expected:
        raise BenchmarkError("IPC received count does not equal expected count")

    for name in (
        "missing",
        "duplicates",
        "corrupted",
        "out_of_range",
    ):
        if required_integer(fields, name) != 0:
            raise BenchmarkError(f"IPC result field {name} is not zero")


def run_once(
    repository_root: Path,
    binary: Path,
    case: BenchmarkCase,
    repetition: int,
) -> Dict[str, object]:
    completed = subprocess.run(
        case.command(binary),
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise BenchmarkError(
            f"{case.name} repetition {repetition} returned "
            f"{completed.returncode}{detail}"
        )

    fields = parse_result_line(completed.stdout)
    require_metadata(case, fields)

    if case.family == "sync":
        validate_sync(case, fields)
        rate_name = "operations_per_second"
    else:
        validate_ipc(case, fields)
        rate_name = "records_per_second"

    elapsed_seconds = required_nonnegative_float(fields, "elapsed_seconds")
    rate = required_nonnegative_float(fields, rate_name)

    return {
        "case": case.name,
        "repetition": repetition,
        "family": case.family,
        "mode": case.mode,
        "workers": fields.get("workers", ""),
        "operations_per_worker": fields.get("operations_per_worker", ""),
        "producers": fields.get("producers", ""),
        "records_per_producer": fields.get("records_per_producer", ""),
        "capacity": fields.get("capacity", ""),
        "expected": fields["expected"],
        "observed": fields.get("observed", ""),
        "received": fields.get("received", ""),
        "lost_updates": fields.get("lost_updates", ""),
        "missing": fields.get("missing", ""),
        "duplicates": fields.get("duplicates", ""),
        "corrupted": fields.get("corrupted", ""),
        "out_of_range": fields.get("out_of_range", ""),
        "validation_pass": fields.get("validation_pass", ""),
        "elapsed_seconds": fields["elapsed_seconds"],
        "rate": fields[rate_name],
        "_elapsed_seconds": elapsed_seconds,
        "_rate": rate,
        "_lost_updates": (
            required_integer(fields, "lost_updates")
            if case.mode == "process-unsafe"
            else None
        ),
    }


def write_raw_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in RAW_COLUMNS})


def write_summary_csv(
    path: Path,
    cases: List[BenchmarkCase],
    repetitions: int,
    rows: List[Dict[str, object]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()

        for case in cases:
            case_rows = [row for row in rows if row["case"] == case.name]
            elapsed_values = [float(row["_elapsed_seconds"]) for row in case_rows]
            rate_values = [float(row["_rate"]) for row in case_rows]
            lost_values = [
                int(row["_lost_updates"])
                for row in case_rows
                if row["_lost_updates"] is not None
            ]

            writer.writerow(
                {
                    "case": case.name,
                    "family": case.family,
                    "mode": case.mode,
                    "workers": case.workers if case.workers is not None else "",
                    "operations_per_worker": (
                        case.operations_per_worker
                        if case.operations_per_worker is not None
                        else ""
                    ),
                    "producers": (
                        case.producers if case.producers is not None else ""
                    ),
                    "records_per_producer": (
                        case.records_per_producer
                        if case.records_per_producer is not None
                        else ""
                    ),
                    "capacity": (
                        case.capacity if case.capacity is not None else ""
                    ),
                    "repetitions": repetitions,
                    "median_elapsed_seconds": (
                        f"{statistics.median(elapsed_values):.6f}"
                    ),
                    "median_rate": f"{statistics.median(rate_values):.6f}",
                    "min_rate": f"{min(rate_values):.6f}",
                    "max_rate": f"{max(rate_values):.6f}",
                    "median_lost_updates": (
                        statistics.median(lost_values) if lost_values else ""
                    ),
                }
            )


def display_path(path: Path, repository_root: Path) -> str:
    try:
        return str(path.relative_to(repository_root))
    except ValueError:
        return str(path)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fixed V1 benchmark suite.")
    parser.add_argument(
        "--repetitions",
        type=positive_integer,
        default=5,
        metavar="N",
        help="number of executions per benchmark case (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        metavar="PATH",
        help="CSV output directory relative to the repository root (default: results)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    repository_root = Path(__file__).resolve().parent.parent
    binary = repository_root / "build" / "linux-concurrency-ipc-release"

    if not binary.is_file():
        print(f"error: release binary not found: {binary}", file=sys.stderr)
        return 1

    output_directory = arguments.output_dir
    if not output_directory.is_absolute():
        output_directory = repository_root / output_directory

    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"error: cannot create output directory: {error}", file=sys.stderr)
        return 1

    cases = benchmark_cases()
    rows: List[Dict[str, object]] = []

    try:
        for case in cases:
            for repetition in range(1, arguments.repetitions + 1):
                print(
                    f"[{repetition}/{arguments.repetitions}] {case.name}",
                    flush=True,
                )
                rows.append(
                    run_once(
                        repository_root,
                        binary,
                        case,
                        repetition,
                    )
                )

        raw_path = output_directory / "benchmark_raw.csv"
        summary_path = output_directory / "benchmark_summary.csv"
        write_raw_csv(raw_path, rows)
        write_summary_csv(
            summary_path,
            cases,
            arguments.repetitions,
            rows,
        )
    except (BenchmarkError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print("Benchmark complete.")
    print(f"Raw results: {display_path(raw_path, repository_root)}")
    print(f"Summary: {display_path(summary_path, repository_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
