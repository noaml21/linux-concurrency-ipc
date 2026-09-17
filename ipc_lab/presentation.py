"""Shared, explicit benchmark wording for the terminal interface."""

from .analysis import Summary


def rate(value: float | None) -> str:
    return "—" if value is None else f"{value:,.1f}"


def relative_bar(value: float | None, maximum: float, width: int = 14) -> str:
    if value is None or maximum <= 0:
        return "—"
    filled = round(width * value / maximum)
    return "━" * filled + "·" * (width - filled)


def detail(summary: Summary) -> str:
    case = summary.case
    count = f"Expected per execution: {case.workers * case.amount:,} • observed range: {summary.observed_min if summary.observed_min is not None else '—'}–{summary.observed_max if summary.observed_max is not None else '—'}"
    if case.family == "ipc":
        counters = " • ".join(f"{key.replace('_', ' ')}: {value:,}" for key, value in summary.counters.items())
        interpretation = "PASS requires every record exactly once with intact content."
    else:
        counters = f"Lost updates (sum across parsed repetitions): {summary.counters['lost_updates']:,}"
        interpretation = ("RACY: attempted operations/sec; zero lost updates does not prove safety."
                          if case.mode == "process-unsafe" else "PASS requires an exact synchronized count and zero lost updates.")
    return f"{case.name} • {summary.correctness}\n{count}\n{counters}\n{interpretation}"
