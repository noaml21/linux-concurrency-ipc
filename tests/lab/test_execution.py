import asyncio
import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ipc_lab.models import Config, MODES
from ipc_lab.records import Attempt, Run, environment, utc_now
from ipc_lab.runner import execute, run_experiment
from ipc_lab.storage import History, compare_runs, deserialize, serialize

from test_core import IPC


ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "build/linux-concurrency-ipc-release"


def example_run():
    config = Config(modes=("pipe",), workers=2, amount=10, repetitions=1)
    return Run(config, environment(BINARY), finished=utc_now(),
               attempts=[Attempt(config.cases()[0], 1, IPC, "", 0)])


class StorageTests(unittest.TestCase):
    def test_round_trip_retains_raw_measurements(self):
        run = example_run()
        loaded = deserialize(serialize(run))
        self.assertEqual(loaded, run)
        self.assertEqual(loaded.summaries(), run.summaries())

    def test_reject_invalid_history(self):
        for mutate in (
            lambda d: d.update(schema_version=99),
            lambda d: d.update(run_id="../../elsewhere"),
            lambda d: d["config"].update(workers=10000),
            lambda d: d["attempts"][0].update(repetition=2),
            lambda d: d["attempts"][0].update(returncode=True),
            lambda d: d["attempts"][0].update(stdout=42),
            lambda d: d.update(attempts=[]),
            lambda d: d.update(system={}),
            lambda d: d.update(started="2026-01-01"),
        ):
            data = json.loads(serialize(example_run()))
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                deserialize(json.dumps(data))
        with self.assertRaises(ValueError):
            deserialize("not json")

    def test_history_and_csv_leave_v1_paths_alone(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            history = History(Path(directory))
            run = example_run()
            path = history.save(run)
            self.assertEqual(history.load(path), run)
            (Path(directory) / "broken.json").write_text("broken")
            runs, errors = history.list_runs()
            self.assertEqual(runs, [run])
            self.assertEqual(len(errors), 1)
            exported = history.export_csv(run)
            with exported.open() as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(rows[0]["median_rate"], "2000.0")
            self.assertEqual(rows[0]["missing_total"], "0")
            self.assertEqual(exported.parent.name, "exports")
            self.assertFalse(list(Path(directory).glob("*.tmp")))
            with self.assertRaises(ValueError):
                history.load(ROOT / "README.md")

    def test_comparison_compatibility_and_zero_rate(self):
        run = example_run()
        newer = deserialize(serialize(run))
        newer.attempts[0] = replace(newer.attempts[0], stdout=IPC.replace("2000.000000", "3000"))
        self.assertEqual(compare_runs(run, newer)[0][3], 50)
        run.attempts[0] = replace(run.attempts[0], stdout=IPC.replace("2000.000000", "0"))
        self.assertIsNone(compare_runs(run, newer)[0][3])
        newer.system["machine"] = "different"
        with self.assertRaises(ValueError):
            compare_runs(run, newer)
        newer.cancelled = True
        with self.assertRaises(ValueError):
            compare_runs(run, newer)


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_all_modes_match_raw_cli_fields(self):
        for family, modes in MODES.items():
            config = Config(family=family, modes=modes, amount=10, repetitions=1)
            events = []
            run = await run_experiment(config, BINARY, asyncio.Event(), events.append)
            self.assertEqual(run.status, "COMPLETE")
            self.assertEqual(len(events), 2 * len(modes))
            self.assertEqual([e.phase for e in events], ["started", "completed"] * len(modes))
            for attempt in run.attempts:
                self.assertFalse(attempt.error)
                raw = dict(token.split("=") for token in attempt.stdout.split())
                for key, value in attempt.measurement.fields.items():
                    self.assertEqual(str(value) if isinstance(value, str) else float(value),
                                     raw[key] if isinstance(value, str) else float(raw[key]))
            self.assertEqual(deserialize(serialize(run)), run)

    async def test_cancel_finishes_current_and_schedules_nothing_else(self):
        config = Config(modes=("shm-ring",), amount=100, repetitions=3)
        cancel = asyncio.Event()
        events = []

        def notify(event):
            events.append(event.phase)
            if event.phase == "started":
                cancel.set()

        run = await run_experiment(config, BINARY, cancel, notify)
        self.assertEqual(run.status, "CANCELLED")
        self.assertEqual(len(run.attempts), 1)
        self.assertEqual(run.attempts[0].correctness, "PASS")
        self.assertEqual(events, ["started", "completed"])

    async def test_cancellation_of_enclosing_task_drains_engine(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(binary, case, repetition):
            entered.set()
            await release.wait()
            return Attempt(case, repetition, IPC, "", 0)

        config = Config(modes=("pipe",), amount=10, repetitions=2)
        with patch("ipc_lab.runner.execute", delayed):
            task = asyncio.create_task(run_experiment(config, BINARY, asyncio.Event()))
            await entered.wait()
            task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            release.set()
            run = await task
        self.assertEqual(run.status, "CANCELLED")
        self.assertEqual(len(run.attempts), 1)

    async def test_failure_and_malformed_output_are_recorded(self):
        config = Config(modes=("pipe",), amount=10, repetitions=1)
        case = config.cases()[0]
        for attempt in (Attempt(case, 1, "", "failure", 1),
                        Attempt(case, 1, "malformed", "", 0)):
            async def fake(*args):
                return attempt
            with patch("ipc_lab.runner.execute", fake):
                run = await run_experiment(config, BINARY, asyncio.Event())
            self.assertEqual(run.status, "FAILED")
            self.assertEqual(run.failures, 1)
            self.assertIsNone(run.summaries()[0].median_rate)
            self.assertEqual(deserialize(serialize(run)), run)
        missing = await execute(ROOT / "build/nonexistent-engine", case, 1)
        self.assertTrue(missing.launch_error)

    async def test_pre_cancelled_run_has_no_executions(self):
        cancel = asyncio.Event()
        cancel.set()
        run = await run_experiment(Config(), BINARY, cancel)
        self.assertEqual(run.attempts, [])
        self.assertEqual(run.status, "CANCELLED")
