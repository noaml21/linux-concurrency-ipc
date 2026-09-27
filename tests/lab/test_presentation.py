import unittest

from ipc_lab.analysis import summarize
from ipc_lab.models import Case
from ipc_lab.parsing import parse_output
from ipc_lab.presentation import detail, rate, relative_bar

from test_core import IPC, SYNC


class PresentationTests(unittest.TestCase):
    def test_missing_rates_and_relative_bars(self):
        self.assertEqual(rate(None), "—")
        self.assertEqual(rate(1234.5), "1,234.5")
        self.assertEqual(relative_bar(5, 10, 4), "━━··")
        self.assertEqual(relative_bar(0, 0), "—")

    def test_correctness_details(self):
        ipc = Case("ipc", "pipe", 2, 10)
        text = detail(summarize(ipc, [parse_output(IPC, ipc)]))
        for counter in ("missing", "duplicates", "corrupted", "out of range"):
            self.assertIn(counter + ": 0", text)
        unsafe = Case("sync", "process-unsafe", 2, 10)
        text = detail(summarize(unsafe, [parse_output(SYNC, unsafe)]))
        self.assertIn("zero lost updates does not prove safety", text)
        self.assertIn("Lost updates", text)
