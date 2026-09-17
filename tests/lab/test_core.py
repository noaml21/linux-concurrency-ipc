import unittest
from dataclasses import replace
from pathlib import Path

from ipc_lab.analysis import summarize
from ipc_lab.models import Case, Config, MODES, RING_CAPACITIES, parse_integer
from ipc_lab.parsing import parse_output


IPC = "family=ipc mode=pipe producers=2 records_per_producer=10 expected=20 received=20 missing=0 duplicates=0 corrupted=0 out_of_range=0 validation_pass=1 elapsed_seconds=0.010000 records_per_second=2000.000000"
SYNC = "family=sync mode=process-unsafe workers=2 operations_per_worker=10 expected=20 observed=17 lost_updates=3 elapsed_seconds=0.010000 operations_per_second=2000.000000"


class ConfigurationTests(unittest.TestCase):
    def test_modes_and_commands(self):
        for family, modes in MODES.items():
            for mode in modes:
                case = Case(family, mode, 2, 10, 8 if mode == "shm-ring" else None)
                expected = ["/engine", family, mode, "2", "10"]
                if mode == "shm-ring":
                    expected.append("8")
                self.assertEqual(case.command(Path("/engine")), expected)

    def test_sweep_expansion(self):
        config = Config(modes=("shm-ring",), sweep=RING_CAPACITIES)
        self.assertEqual(tuple(c.capacity for c in config.cases()), RING_CAPACITIES)
        self.assertEqual(config.total, 18)

    def test_invalid_configurations(self):
        for changes in ({"workers": 0}, {"workers": True}, {"amount": -1},
                        {"amount": 1.5}, {"workers": 33}, {"amount": 100001},
                        {"workers": 32, "amount": 100000}, {"repetitions": 16},
                        {"capacity": 32768}, {"modes": ()}, {"modes": ("pipe;id",)},
                        {"modes": ("pipe", "pipe")}, {"family": "bad"},
                        {"sweep": (1, 1)}, {"sweep": (0,)},
                        {"modes": ("pipe",), "sweep": (1, 2)},
                        {"sweep": tuple(range(1, 9)), "repetitions": 15},
                        {"workers": 2, "amount": 100000, "repetitions": 15}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(Config(), **changes)

    def test_input_cannot_inject_commands(self):
        for value in ("; id", "$(id)", "1 2", "--help", "1.0", "-1", "١", "9" * 100, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_integer(value, "Workers", 32)
        self.assertEqual(parse_integer(" 02 ", "Workers", 32), 2)


class ParsingTests(unittest.TestCase):
    case = Case("ipc", "pipe", 2, 10)

    def test_valid_fields_match_output(self):
        m = parse_output(IPC + "\n", self.case)
        self.assertEqual(m.correctness, "PASS")
        self.assertEqual(m.fields["received"], 20)
        self.assertEqual(m.rate, 2000)

    def test_reject_malformed_or_mismatched(self):
        for value in ("", IPC + "\n" + IPC, IPC + " expected=20", IPC + " bad",
                      IPC.replace("expected=20", "expected=-1"),
                      IPC.replace("producers=2", "producers=3"),
                      IPC.replace("mode=pipe", "mode=fifo"),
                      IPC.replace("expected=20", "expected=21"),
                      IPC.replace("received=20", "received=19"),
                      IPC.replace("2000.000000", "nan"),
                      IPC.replace("2000.000000", "inf"),
                      IPC.replace("2000.000000", "-1"),
                      IPC.replace("validation_pass=1", "validation_pass=2"),
                      IPC.replace("missing=0 ", "")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_output(value, self.case)

    def test_correctness_failure_is_preserved(self):
        output = IPC.replace("received=20", "received=19").replace("missing=0", "missing=1").replace("validation_pass=1", "validation_pass=0")
        self.assertEqual(parse_output(output, self.case).correctness, "FAIL")

    def test_unsafe_is_never_claimed_correct(self):
        case = Case("sync", "process-unsafe", 2, 10)
        self.assertEqual(parse_output(SYNC, case).correctness, "RACY")
        exact = SYNC.replace("observed=17", "observed=20").replace("lost_updates=3", "lost_updates=0")
        self.assertEqual(parse_output(exact, case).correctness, "RACY")
        safe = SYNC.replace("process-unsafe", "threads-mutex")
        self.assertEqual(parse_output(safe, replace(case, mode="threads-mutex")).correctness, "FAIL")
        with self.assertRaises(ValueError):
            parse_output(SYNC.replace("lost_updates=3", "lost_updates=2"), case)

    def test_ring_capacity_metadata(self):
        output = IPC.replace("mode=pipe", "mode=shm-ring capacity=8")
        parse_output(output, replace(self.case, mode="shm-ring", capacity=8))
        with self.assertRaises(ValueError):
            parse_output(output, replace(self.case, mode="shm-ring", capacity=64))

    def test_statistics_and_failure_exclusion(self):
        values = [parse_output(IPC.replace("2000.000000", str(rate)), self.case) for rate in (10, 40, 20, 30)]
        failed = parse_output(IPC.replace("corrupted=0", "corrupted=1").replace("validation_pass=1", "validation_pass=0"), self.case)
        summary = summarize(self.case, values + [failed], errors=1)
        self.assertEqual((summary.median_rate, summary.min_rate, summary.max_rate), (25, 10, 40))
        self.assertEqual((summary.accepted, summary.failures, summary.correctness), (4, 2, "FAIL"))
        self.assertEqual(summary.counters["corrupted"], 1)
        self.assertIsNone(summarize(self.case, []).median_rate)
        self.assertEqual(summarize(self.case, []).correctness, "NOT RUN")
        with self.assertRaises(ValueError):
            summarize(replace(self.case, amount=11), values)


if __name__ == "__main__":
    unittest.main()
