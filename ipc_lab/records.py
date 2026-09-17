"""Run records retain original engine output; summaries are always derived."""

import hashlib
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .analysis import Summary, summarize
from .models import Case, Config
from .parsing import Measurement, parse_output


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def environment(binary: Path) -> dict[str, str]:
    return {
        "system": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "cpu_count": str(os.cpu_count()),
        "python": platform.python_version(), "engine": binary.name,
        "engine_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }


@dataclass(frozen=True)
class Attempt:
    case: Case
    repetition: int
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    launch_error: str = ""

    @property
    def error(self) -> str:
        if self.launch_error:
            return self.launch_error
        if self.returncode != 0:
            return f"Engine exit {self.returncode}: {self.stderr.strip()}"
        try:
            parse_output(self.stdout, self.case)
        except ValueError as error:
            return str(error)
        return ""

    @property
    def measurement(self) -> Measurement | None:
        return None if self.error else parse_output(self.stdout, self.case)

    @property
    def correctness(self) -> str:
        measurement = self.measurement
        return measurement.correctness if measurement else "ERROR"


@dataclass
class Run:
    config: Config
    system: dict[str, str]
    run_id: str = field(default_factory=lambda: uuid4().hex)
    started: str = field(default_factory=utc_now)
    finished: str | None = None
    cancelled: bool = False
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def failures(self) -> int:
        return sum(a.correctness in ("ERROR", "FAIL") for a in self.attempts)

    @property
    def status(self) -> str:
        if self.finished is None:
            return "INCOMPLETE"
        if self.cancelled:
            return "CANCELLED"
        return "FAILED" if self.failures else "COMPLETE"

    def summaries(self) -> list[Summary]:
        summaries = []
        for case in self.config.cases():
            attempts = [a for a in self.attempts if a.case == case]
            measurements = [a.measurement for a in attempts]
            summaries.append(summarize(case, [m for m in measurements if m is not None],
                                       sum(m is None for m in measurements)))
        return summaries
