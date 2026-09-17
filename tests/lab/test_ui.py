import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Checkbox, DataTable, Input, Select, SelectionList, Static, TabbedContent

from ipc_lab.app import LabApp
from ipc_lab.models import MODES
from ipc_lab.runner import execute

from test_execution import BINARY, ROOT


class UITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "build")
        self.addCleanup(self.temporary.cleanup)
        self.app = LabApp(BINARY, Path(self.temporary.name))

    async def finish(self, pilot):
        await self.app.workers.wait_for_complete()
        await pilot.pause()

    async def test_real_ipc_workflow_export_history(self):
        async with self.app.run_test(size=(100, 36)) as pilot:
            self.app.query_one("#amount", Input).value = "10"
            self.app.query_one("#repetitions", Input).value = "1"
            await pilot.click("#run")
            await self.finish(pilot)
            self.assertEqual(self.app.current.status, "COMPLETE")
            self.assertEqual(len(self.app.current.attempts), 4)
            self.assertEqual(self.app.query_one("#summary", DataTable).row_count, 4)
            self.assertEqual(self.app.query_one("#tabs", TabbedContent).active, "results")
            await pilot.click("#export")
            await self.finish(pilot)
            self.assertEqual(len(list(Path(self.temporary.name).glob("exports/*.csv"))), 1)
            saved = self.app.current.run_id
            self.app.query_one("#tabs", TabbedContent).active = "history"
            await pilot.pause()
            await pilot.click("#open-history")
            self.assertEqual(self.app.current.run_id, saved)
            self.assertEqual(self.app.query_one("#tabs", TabbedContent).active, "results")

    async def test_invalid_input_never_launches(self):
        async with self.app.run_test() as pilot:
            self.app.query_one("#workers", Input).value = "1; touch injected"
            with patch("ipc_lab.app.run_experiment") as runner:
                await pilot.click("#run")
                runner.assert_not_called()
            self.assertFalse(self.app.running)
            self.assertIn("decimal digits", self.app.last_error)
            self.assertIsNone(self.app.current)

    async def test_real_sync_and_capacity_sweep(self):
        async with self.app.run_test(size=(100, 36)) as pilot:
            self.app.query_one("#amount", Input).value = "10"
            self.app.query_one("#repetitions", Input).value = "1"
            self.app.query_one("#family", Select).value = "sync"
            await pilot.pause()
            await pilot.click("#run")
            await self.finish(pilot)
            self.assertEqual(self.app.current.status, "COMPLETE")
            self.assertEqual([a.case.mode for a in self.app.current.attempts], list(MODES["sync"]))
            self.assertEqual(self.app.current.attempts[0].correctness, "RACY")
            self.app.query_one("#tabs", TabbedContent).active = "configure"
            self.app.query_one("#family", Select).value = "ipc"
            await pilot.pause()
            selections = self.app.query_one("#mechanisms", SelectionList)
            selections.deselect_all()
            self.app.query_one("#sweep", Checkbox).value = True
            await pilot.pause()
            await pilot.click("#run")
            await self.finish(pilot)
            self.assertEqual(self.app.current.status, "COMPLETE")
            self.assertEqual(len(self.app.current.attempts), 6)
            self.assertEqual(self.app.current.attempts[-1].case.capacity, 1024)

    async def test_ui_cancel_is_responsive_and_drains(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(binary, case, repetition):
            entered.set()
            await release.wait()
            return await execute(binary, case, repetition)

        async with self.app.run_test() as pilot:
            self.app.query_one("#amount", Input).value = "10"
            with patch("ipc_lab.runner.execute", delayed):
                await pilot.click("#run")
                await entered.wait()
                await pilot.press("ctrl+x")
                self.assertTrue(self.app.cancel_event.is_set())
                self.assertTrue(self.app.running)
                release.set()
                await self.finish(pilot)
            self.assertEqual(self.app.current.status, "CANCELLED")
            self.assertEqual(len(self.app.current.attempts), 1)
            self.assertEqual(self.app.current.attempts[0].correctness, "PASS")

    async def test_small_terminal_keyboard_navigation(self):
        async with self.app.run_test(size=(60, 20)) as pilot:
            self.app.query_one("#amount", Input).value = "5"
            self.app.query_one("#repetitions", Input).value = "1"
            await pilot.press("ctrl+r")
            await self.finish(pilot)
            self.assertEqual(self.app.current.status, "COMPLETE")
            self.app.query_one("#summary", DataTable).focus()
            await pilot.press("down", "right")
            self.assertEqual(self.app.query_one("#summary", DataTable).cursor_row, 1)

    async def test_storage_failure_keeps_results_for_retry(self):
        async with self.app.run_test() as pilot:
            self.app.query_one("#amount", Input).value = "5"
            self.app.query_one("#repetitions", Input).value = "1"
            with patch.object(self.app.history, "save", side_effect=OSError("disk full")):
                await pilot.click("#run")
                await self.finish(pilot)
            self.assertEqual(self.app.current.status, "COMPLETE")
            self.assertIn("History save failed", str(self.app.query_one("#result-message", Static).content))
            await pilot.click("#save")
            await self.finish(pilot)
            self.assertEqual(len(list(Path(self.temporary.name).glob("*.json"))), 1)

    async def test_history_comparison(self):
        async with self.app.run_test(size=(100, 36)) as pilot:
            self.app.query_one("#amount", Input).value = "5"
            self.app.query_one("#repetitions", Input).value = "1"
            for _ in range(2):
                self.app.query_one("#tabs", TabbedContent).active = "configure"
                await pilot.pause()
                await pilot.click("#run")
                await self.finish(pilot)
            self.app.query_one("#tabs", TabbedContent).active = "history"
            await pilot.pause()
            await pilot.click("#pin")
            table = self.app.query_one("#history-table", DataTable)
            table.focus()
            await pilot.press("down")
            await pilot.click("#compare")
            self.assertEqual(self.app.query_one("#comparison", DataTable).row_count, 4)
