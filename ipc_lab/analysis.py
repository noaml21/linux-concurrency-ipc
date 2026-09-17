"""Descriptive statistics, keeping measurement validity separate from speed."""

from dataclasses import dataclass
from statistics import median

from .models import Case
from .parsing import COUNTERS, Measurement


@dataclass(frozen=True)
class Summary:
    case: Case
    accepted: int
    failures: int
    correctness: str
    median_rate: float | None
    min_rate: float | None
    max_rate: float | None
    counters: dict[str, int]
    observed_min: int | None
    observed_max: int | None
    rates: tuple[float, ...]


def summarize(case: Case, measurements: list[Measurement], errors: int = 0) -> Summary:
    if any(m.case != case for m in measurements):
        raise ValueError("Cannot aggregate different workloads")
    rates = tuple(m.rate for m in measurements if m.correctness != "FAIL")
    failures = errors + sum(m.correctness == "FAIL" for m in measurements)
    status = "FAIL" if failures else ("RACY" if case.mode == "process-unsafe" else "PASS")
    if not measurements and not errors:
        status = "NOT RUN"
    names = COUNTERS if case.family == "ipc" else ("lost_updates",)
    counters = {key: sum(int(m.fields[key]) for m in measurements) for key in names}
    observed = [int(m.fields["received" if case.family == "ipc" else "observed"]) for m in measurements]
    return Summary(case, len(rates), failures, status,
                   median(rates) if rates else None,
                   min(rates) if rates else None, max(rates) if rates else None,
                   counters, min(observed) if observed else None,
                   max(observed) if observed else None, rates)
