"""Validated workloads and deterministic case expansion (no UI dependencies)."""

from dataclasses import dataclass
from pathlib import Path
import random


MODES = {
    "ipc": ("pipe", "fifo", "shm-mailbox", "shm-ring"),
    "sync": ("process-unsafe", "threads-mutex", "process-sem"),
}
AVAILABLE_MODES = {**MODES, "ipc": (*MODES["ipc"], "shm-ring-batch")}
RING_CAPACITIES = (1, 2, 8, 64, 256, 1024)


def bounded_integer(value: int, name: str, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 1 to {maximum:,}")


def parse_integer(text: str, name: str, maximum: int) -> int:
    text = text.strip()
    if not text or not text.isascii() or not text.isdecimal() or len(text) > 9:
        raise ValueError(f"{name} must contain decimal digits only")
    value = int(text)
    bounded_integer(value, name, maximum)
    return value


@dataclass(frozen=True)
class Case:
    family: str
    mode: str
    workers: int
    amount: int
    capacity: int | None = None
    batch_size: int | None = None

    def __post_init__(self) -> None:
        if self.family not in MODES or self.mode not in AVAILABLE_MODES[self.family]:
            raise ValueError("Choose a supported experiment mechanism")
        bounded_integer(self.workers, "Workers/producers", 32)
        bounded_integer(self.amount, "Items per worker/producer", 100_000)
        if self.workers * self.amount > 200_000:
            raise ValueError("Limit each execution to 200,000 total items")
        if self.mode in ("shm-ring", "shm-ring-batch"):
            bounded_integer(self.capacity, "Ring capacity", 32767)
        elif self.capacity is not None:
            raise ValueError("Capacity applies only to ring modes")
        if self.mode == "shm-ring-batch":
            bounded_integer(self.batch_size, "Batch size", self.capacity)
        elif self.batch_size is not None:
            raise ValueError("Batch size applies only to shm-ring-batch")

    @property
    def name(self) -> str:
        suffix = f" / cap {self.capacity}" if self.capacity is not None else ""
        batch = f" / batch {self.batch_size}" if self.batch_size is not None else ""
        return self.mode + suffix + batch + f" / {self.workers} × {self.amount}"

    def command(self, binary: Path) -> list[str]:
        args = [str(binary), self.family, self.mode, str(self.workers), str(self.amount)]
        if self.capacity is not None:
            args.append(str(self.capacity))
        if self.batch_size is not None:
            args.append(str(self.batch_size))
        return args


@dataclass(frozen=True)
class Config:
    family: str = "ipc"
    modes: tuple[str, ...] = MODES["ipc"]
    workers: int = 2
    amount: int = 2000
    repetitions: int = 3
    capacity: int = 64
    sweep: tuple[int, ...] = ()
    worker_matrix: tuple[int, ...] = ()
    amount_matrix: tuple[int, ...] = ()
    warmups: int = 0
    seed: int = 2026
    interleave: bool = False
    deadline_ms: int = 30000
    batch_size: int = 8

    def __post_init__(self) -> None:
        if self.family not in MODES:
            raise ValueError("Choose IPC or synchronization")
        if not isinstance(self.modes, tuple) or not self.modes:
            raise ValueError("Select at least one mechanism")
        if any(mode not in AVAILABLE_MODES[self.family] for mode in self.modes):
            raise ValueError("Mechanisms must belong to the selected experiment")
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("Mechanisms must not be repeated")
        bounded_integer(self.repetitions, "Repetitions", 15)
        bounded_integer(self.capacity, "Ring capacity", 32767)
        if not isinstance(self.sweep, tuple) or len(self.sweep) > 8:
            raise ValueError("A sweep can contain at most 8 capacities")
        for value in self.sweep:
            bounded_integer(value, "Sweep capacity", 32767)
        if len(set(self.sweep)) != len(self.sweep):
            raise ValueError("Sweep capacities must not be repeated")
        if self.sweep and not any(mode.startswith("shm-ring") for mode in self.modes):
            raise ValueError("Select shm-ring to sweep capacity")
        for values, name, maximum in ((self.worker_matrix, "Worker matrix", 32),
                                      (self.amount_matrix, "Amount matrix", 100000)):
            if not isinstance(values, tuple) or len(values) > 8 or len(set(values)) != len(values):
                raise ValueError(f"{name} requires at most 8 distinct values")
            for value in values:
                bounded_integer(value, name, maximum)
        if type(self.warmups) is not int or not 0 <= self.warmups <= 3:
            raise ValueError("Warmups must be 0..3")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("Seed must be 0..2^32-1")
        if type(self.interleave) is not bool:
            raise ValueError("Interleave must be boolean")
        bounded_integer(self.deadline_ms, "Deadline milliseconds", 120000)
        bounded_integer(self.batch_size, "Batch size", 32767)
        cases = self.cases()
        if len(cases) * (self.repetitions + self.warmups) > 90:
            raise ValueError("Limit the experiment to 90 executions")
        if sum(c.workers * c.amount for c in cases) * (self.repetitions + self.warmups) > 5_000_000:
            raise ValueError("Limit the experiment to 5,000,000 total items")

    def cases(self) -> tuple[Case, ...]:
        cases = []
        for mode in self.modes:
            capacities = (self.sweep or (self.capacity,)) if mode.startswith("shm-ring") else (None,)
            cases.extend(Case(self.family, mode, workers, amount, cap,
                              min(self.batch_size, cap) if mode == "shm-ring-batch" else None)
                         for workers in (self.worker_matrix or (self.workers,))
                         for amount in (self.amount_matrix or (self.amount,))
                         for cap in capacities)
        return tuple(cases)

    @property
    def total(self) -> int:
        return len(self.cases()) * (self.repetitions + self.warmups)

    def schedule(self) -> tuple[tuple[Case, int], ...]:
        rng = random.Random(self.seed)
        schedule = []
        if not self.interleave:
            return tuple((case, rep) for case in self.cases()
                         for rep in (*range(-self.warmups, 0), *range(1, self.repetitions + 1)))
        for rep in (*range(-self.warmups, 0), *range(1, self.repetitions + 1)):
            block = list(self.cases())
            rng.shuffle(block)
            schedule.extend((case, rep) for case in block)
        return tuple(schedule)
