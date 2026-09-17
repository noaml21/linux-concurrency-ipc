"""Validated workloads and deterministic case expansion (no UI dependencies)."""

from dataclasses import dataclass
from pathlib import Path


MODES = {
    "ipc": ("pipe", "fifo", "shm-mailbox", "shm-ring"),
    "sync": ("process-unsafe", "threads-mutex", "process-sem"),
}
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

    def __post_init__(self) -> None:
        if self.family not in MODES or self.mode not in MODES[self.family]:
            raise ValueError("Choose a supported experiment mechanism")
        bounded_integer(self.workers, "Workers/producers", 32)
        bounded_integer(self.amount, "Items per worker/producer", 100_000)
        if self.workers * self.amount > 200_000:
            raise ValueError("Limit each execution to 200,000 total items")
        if self.mode == "shm-ring":
            bounded_integer(self.capacity, "Ring capacity", 32767)
        elif self.capacity is not None:
            raise ValueError("Capacity applies only to shm-ring")

    @property
    def name(self) -> str:
        suffix = f" / cap {self.capacity}" if self.capacity is not None else ""
        return self.mode + suffix

    def command(self, binary: Path) -> list[str]:
        args = [str(binary), self.family, self.mode, str(self.workers), str(self.amount)]
        if self.capacity is not None:
            args.append(str(self.capacity))
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

    def __post_init__(self) -> None:
        if self.family not in MODES:
            raise ValueError("Choose IPC or synchronization")
        if not isinstance(self.modes, tuple) or not self.modes:
            raise ValueError("Select at least one mechanism")
        if any(mode not in MODES[self.family] for mode in self.modes):
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
        if self.sweep and "shm-ring" not in self.modes:
            raise ValueError("Select shm-ring to sweep capacity")
        cases = self.cases()
        if len(cases) * self.repetitions > 90:
            raise ValueError("Limit the experiment to 90 executions")
        if self.workers * self.amount * len(cases) * self.repetitions > 5_000_000:
            raise ValueError("Limit the experiment to 5,000,000 total items")

    def cases(self) -> tuple[Case, ...]:
        cases = []
        for mode in self.modes:
            capacities = (self.sweep or (self.capacity,)) if mode == "shm-ring" else (None,)
            cases.extend(Case(self.family, mode, self.workers, self.amount, cap)
                         for cap in capacities)
        return tuple(cases)

    @property
    def total(self) -> int:
        return len(self.cases()) * self.repetitions
