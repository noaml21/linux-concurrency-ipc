#!/usr/bin/env python3

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


class StressError(Exception):
    pass


@dataclass(frozen=True)
class StressCase:
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


def stress_cases() -> List[StressCase]:
    cases = [
        StressCase("sync-threads-mutex", "sync", "threads-mutex", 8, 250000),
        StressCase("sync-process-sem", "sync", "process-sem", 8, 25000),
        StressCase(
            "ipc-pipe",
            "ipc",
            "pipe",
            producers=8,
            records_per_producer=50000,
        ),
        StressCase(
            "ipc-fifo",
            "ipc",
            "fifo",
            producers=8,
            records_per_producer=50000,
        ),
        StressCase(
            "ipc-shm-mailbox",
            "ipc",
            "shm-mailbox",
            producers=8,
            records_per_producer=50000,
        ),
    ]

    for capacity in (1, 2, 8, 64, 256, 1024):
        cases.append(
            StressCase(
                f"ipc-shm-ring-cap{capacity}",
                "ipc",
                "shm-ring",
                producers=8,
                records_per_producer=50000,
                capacity=capacity,
            )
        )

    return cases


def parse_result_line(stdout: str) -> Dict[str, str]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StressError(
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
            raise StressError(f"malformed result field: {token!r}")
        fields[key] = value

    return fields


def required_integer(fields: Dict[str, str], name: str) -> int:
    if name not in fields:
        raise StressError(f"missing result field: {name}")

    try:
        value = int(fields[name], 10)
    except ValueError as error:
        raise StressError(f"result field {name} is not an integer") from error

    if value < 0:
        raise StressError(f"result field {name} must not be negative")
    return value


def validate_metadata(case: StressCase, fields: Dict[str, str]) -> None:
    if fields.get("family") != case.family:
        raise StressError("result family does not match the requested case")
    if fields.get("mode") != case.mode:
        raise StressError("result mode does not match the requested case")

    if case.family == "sync":
        if required_integer(fields, "workers") != case.workers:
            raise StressError("result workers does not match the requested workload")
        if (
            required_integer(fields, "operations_per_worker")
            != case.operations_per_worker
        ):
            raise StressError(
                "result operations_per_worker does not match the requested workload"
            )
    else:
        if required_integer(fields, "producers") != case.producers:
            raise StressError("result producers does not match the requested workload")
        if (
            required_integer(fields, "records_per_producer")
            != case.records_per_producer
        ):
            raise StressError(
                "result records_per_producer does not match the requested workload"
            )
        if case.capacity is not None:
            if required_integer(fields, "capacity") != case.capacity:
                raise StressError(
                    "result capacity does not match the requested workload"
                )


def validate_sync(case: StressCase, fields: Dict[str, str]) -> None:
    expected = required_integer(fields, "expected")
    observed = required_integer(fields, "observed")
    lost_updates = required_integer(fields, "lost_updates")

    if expected != case.workers * case.operations_per_worker:
        raise StressError("sync expected count does not match the workload")
    if observed != expected:
        raise StressError("synchronized observed count does not equal expected count")
    if lost_updates != 0:
        raise StressError("synchronized mode reported lost updates")


def validate_ipc(case: StressCase, fields: Dict[str, str]) -> None:
    expected = required_integer(fields, "expected")
    received = required_integer(fields, "received")

    if expected != case.producers * case.records_per_producer:
        raise StressError("IPC expected count does not match the workload")
    if required_integer(fields, "validation_pass") != 1:
        raise StressError("IPC validation_pass is not 1")
    if received != expected:
        raise StressError("IPC received count does not equal expected count")

    for name in (
        "missing",
        "duplicates",
        "corrupted",
        "out_of_range",
    ):
        if required_integer(fields, name) != 0:
            raise StressError(f"IPC result field {name} is not zero")


def run_case(repository_root: Path, binary: Path, case: StressCase) -> None:
    try:
        completed = subprocess.run(
            case.command(binary),
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise StressError(
            f"{case.name} exceeded the 120 second timeout"
        ) from error
    except OSError as error:
        raise StressError(f"could not execute {case.name}: {error}") from error

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise StressError(
            f"{case.name} returned {completed.returncode}{detail}"
        )

    fields = parse_result_line(completed.stdout)
    validate_metadata(case, fields)

    if case.family == "sync":
        validate_sync(case, fields)
    else:
        validate_ipc(case, fields)


def main() -> int:
    repository_root = Path(__file__).resolve().parent.parent
    binary = repository_root / "build" / "linux-concurrency-ipc-release"

    if not binary.is_file():
        print(f"error: release binary not found: {binary}", file=sys.stderr)
        return 1

    for case in stress_cases():
        print(f"RUN  {case.name}", flush=True)
        try:
            run_case(repository_root, binary, case)
        except StressError as error:
            print(f"error: {case.name}: {error}", file=sys.stderr)
            return 1
        print(f"PASS {case.name}", flush=True)

    print("Stress suite: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
