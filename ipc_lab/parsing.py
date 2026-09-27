"""Strict CLI contract parsing; preserve correctness failures as observations."""

import math
import re
from dataclasses import dataclass

from .models import Case


COUNTERS = ("missing", "duplicates", "corrupted", "out_of_range")


@dataclass(frozen=True)
class Measurement:
    case: Case
    fields: dict[str, str | int | float]
    correctness: str

    @property
    def rate(self) -> float:
        key = "records_per_second" if self.case.family == "ipc" else "operations_per_second"
        return float(self.fields[key])


def parse_output(stdout: str, case: Case) -> Measurement:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("Expected exactly one non-empty engine output line")
    fields = {}
    for token in lines[0].split():
        key, separator, value = token.partition("=")
        if separator != "=" or not key or not value or "=" in value or key in fields:
            raise ValueError(f"Malformed or duplicate engine field: {token!r}")
        fields[key] = value

    if fields.get("family") != case.family or fields.get("mode") != case.mode:
        raise ValueError("Engine family/mode does not match the requested case")
    integer_names = ["expected"]
    if case.family == "ipc":
        integer_names += ["producers", "records_per_producer", "received", "validation_pass", *COUNTERS]
        rate_name = "records_per_second"
        metadata = {"producers": case.workers, "records_per_producer": case.amount}
    else:
        integer_names += ["workers", "operations_per_worker", "observed", "lost_updates"]
        rate_name = "operations_per_second"
        metadata = {"workers": case.workers, "operations_per_worker": case.amount}
    if case.capacity is not None:
        integer_names.append("capacity")
        metadata["capacity"] = case.capacity
    if case.batch_size is not None:
        integer_names.append("batch_size")
        metadata["batch_size"] = case.batch_size
    required = {"family", "mode", "elapsed_seconds", rate_name, *integer_names}
    if set(fields) != required:
        raise ValueError(f"Unexpected engine fields: missing={required - fields.keys()}, extra={fields.keys() - required}")
    parsed: dict[str, str | int | float] = dict(fields)
    for key in integer_names:
        value = fields[key]
        if not re.fullmatch(r"[0-9]{1,20}", value):
            raise ValueError(f"Engine field {key} must be a nonnegative integer")
        parsed[key] = int(value)
    for key in ("elapsed_seconds", rate_name):
        value = float(fields[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Engine field {key} must be finite and nonnegative")
        parsed[key] = value
    if any(parsed[key] != value for key, value in metadata.items()):
        raise ValueError("Engine workload metadata does not match the requested case")
    if parsed["expected"] != case.workers * case.amount:
        raise ValueError("Engine expected count does not match the workload")
    if case.family == "ipc":
        if parsed["validation_pass"] not in (0, 1):
            raise ValueError("validation_pass must be 0 or 1")
        passed = parsed["received"] == parsed["expected"] and all(parsed[k] == 0 for k in COUNTERS)
        if bool(parsed["validation_pass"]) != passed:
            raise ValueError("Engine validation flag contradicts its counters")
        if (parsed["missing"] > parsed["expected"] or
                parsed["received"] != parsed["expected"] - parsed["missing"] + parsed["duplicates"] + parsed["out_of_range"] or
                parsed["corrupted"] > parsed["received"] - parsed["out_of_range"]):
            raise ValueError("Engine validation counters are inconsistent")
        correctness = "PASS" if passed else "FAIL"
    else:
        if parsed["observed"] > parsed["expected"] or parsed["lost_updates"] != parsed["expected"] - parsed["observed"]:
            raise ValueError("Engine synchronization counters are inconsistent")
        correctness = "RACY" if case.mode == "process-unsafe" else ("PASS" if parsed["lost_updates"] == 0 else "FAIL")
    return Measurement(case, parsed, correctness)
