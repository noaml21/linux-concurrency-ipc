import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ipc_lab.models import Config
from ipc_lab.records import Run, environment
from ipc_lab.runner import run_experiment
from ipc_lab.storage import History, deserialize, serialize
from test_execution import ROOT, BINARY, example_run


class MatrixTests(unittest.TestCase):
    def test_seeded_interleaved_schedule_and_bounds(self):
        config = Config(modes=("pipe", "shm-ring"), worker_matrix=(1, 2),
                        amount_matrix=(10, 100), sweep=(1, 8), warmups=1,
                        repetitions=2, interleave=True, seed=17)
        self.assertEqual(config.schedule(), replace(config).schedule())
        self.assertNotEqual(config.schedule(), replace(config, seed=18).schedule())
        self.assertEqual(len(config.schedule()), config.total)
        self.assertEqual(len(set(config.schedule())), config.total)
        self.assertTrue(all(rep == -1 for _, rep in config.schedule()[:len(config.cases())]))
        for changes in ({"worker_matrix": (1, 1)}, {"amount_matrix": (0,)},
                        {"worker_matrix": (1, 2, 4, 8), "amount_matrix": (1000, 10000), "repetitions": 15},
                        {"warmups": 4}, {"seed": -1}, {"deadline_ms": 120001}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(config, **changes)

    def test_v2_schema_explicit_migration(self):
        data = json.loads(serialize(example_run()))
        data["schema_version"] = 1
        for name in ("worker_matrix", "amount_matrix", "warmups", "seed", "interleave", "deadline_ms"):
            data["config"].pop(name)
        for attempt in data["attempts"]:
            attempt.pop("command")
            attempt.pop("wall_seconds")
        for key in tuple(data["system"]):
            if key not in {"system", "release", "machine", "cpu_count", "python", "engine", "engine_sha256"}:
                data["system"].pop(key)
        migrated = deserialize(json.dumps(data))
        self.assertEqual(migrated.status, "COMPLETE")
        self.assertFalse(migrated.config.interleave)
        self.assertEqual(migrated.summaries()[0].accepted, 1)
        self.assertEqual(deserialize(serialize(migrated)), migrated)


class DurableExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_incremental_recovery_and_warmup_exclusion(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            history = History(Path(directory))
            checkpoints = []
            def save(run):
                checkpoints.append(history.load(history.save(run)))
            config = Config(modes=("shm-ring",), amount=20, warmups=1, repetitions=2)
            run = await run_experiment(config, BINARY, asyncio.Event(), checkpoint=save)
            self.assertEqual([len(r.attempts) for r in checkpoints], [0, 1, 2, 3, 3])
            self.assertEqual(checkpoints[2].status, "INCOMPLETE")
            self.assertEqual(run.summaries()[0].accepted, 2)
            self.assertTrue(all(a.command and a.wall_seconds >= 0 for a in run.attempts))
            self.assertEqual(deserialize(serialize(run)), run)

    async def test_active_engine_cancellation_and_deadline(self):
        # Real C engine, long workload, not a mocked sleep or parent-only timeout.
        for mode in ("shm-ring", "shm-mailbox", "fifo", "pipe", "process-sem", "threads-mutex"):
            family = "sync" if mode in ("process-sem", "threads-mutex") else "ipc"
            config = Config(family=family, modes=(mode,), amount=100000, workers=2,
                            repetitions=2, deadline_ms=1)
            run = await run_experiment(config, BINARY, asyncio.Event())
            self.assertEqual(run.status, "FAILED", mode)
            self.assertIsNone(run.summaries()[0].median_rate)
        cancel = asyncio.Event()
        config = Config(modes=("shm-mailbox",), amount=100000, workers=2, repetitions=2)
        entered = asyncio.Event()
        task = asyncio.create_task(run_experiment(config, BINARY, cancel,
                                  lambda event: entered.set() if event.phase == "started" else None))
        await asyncio.wait_for(entered.wait(), 3)
        await asyncio.sleep(0.1)
        cancel.set()
        run = await asyncio.wait_for(task, 3)
        self.assertEqual(run.status, "CANCELLED")
        self.assertEqual(len(run.attempts), 1)
        self.assertIsNone(run.attempts[0].measurement)


class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_roundtrip_parser_export(self):
        import csv
        from ipc_lab.models import Case
        from ipc_lab.parsing import parse_output
        config = Config(modes=("shm-ring", "shm-ring-batch"), amount=31,
                        sweep=(1, 2, 8), batch_size=3, repetitions=2,
                        warmups=1, interleave=True)
        run = await run_experiment(config, BINARY, asyncio.Event())
        self.assertEqual(run.status, "COMPLETE")
        self.assertEqual(deserialize(serialize(run)), run)
        self.assertEqual([s.accepted for s in run.summaries()], [2] * 6)
        self.assertEqual([c.batch_size for c in config.cases() if c.batch_size], [1, 2, 3])
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            path = History(Path(directory)).export_csv(run)
            with path.open() as source:
                rows = list(csv.DictReader(source))
            self.assertEqual([r["batch_size"] for r in rows], ["", "", "", "1", "2", "3"])
        attempt = next(a for a in run.attempts if a.case.batch_size == 3)
        with self.assertRaises(ValueError):
            parse_output(attempt.stdout.replace("batch_size=3", "batch_size=2"), attempt.case)
        for case in (("ipc", "shm-ring-batch", 2, 10, 2, 3),
                     ("ipc", "pipe", 2, 10, None, 1)):
            with self.assertRaises(ValueError):
                Case(*case)

    async def test_batch_ui_configuration_and_run(self):
        from ipc_lab.app import LabApp
        from textual.widgets import Input, SelectionList
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            app = LabApp(BINARY, Path(directory))
            async with app.run_test(size=(100, 36)) as pilot:
                app.query_one("#mechanisms", SelectionList).deselect_all()
                app.query_one("#mechanisms", SelectionList).select("shm-ring-batch")
                app.query_one("#amount", Input).value = "31"
                app.query_one("#repetitions", Input).value = "1"
                app.query_one("#capacity", Input).value = "2"
                await pilot.press("ctrl+r")
                await app.workers.wait_for_complete()
                self.assertEqual(app.current.status, "COMPLETE")
                self.assertEqual(app.current.attempts[0].case.batch_size, 2)


class ProvenanceTests(unittest.TestCase):
    def test_build_digest_mismatch_is_not_trusted(self):
        import shutil
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            binary = Path(directory) / "engine"
            shutil.copyfile(BINARY, binary)
            binary.with_suffix(".build.json").write_text(json.dumps({
                "engine_sha256": "0" * 64, "compiler": "not-the-real-compiler"}))
            metadata = environment(binary)
            self.assertEqual(metadata["compiler"], "unavailable")
            self.assertNotEqual(metadata["engine_sha256"], "0" * 64)

    def test_optional_perf_unavailability_and_distribution_report(self):
        from ipc_lab.experiment import perf_probe, report
        run = example_run()
        with patch("ipc_lab.experiment.shutil.which", return_value=None):
            probe = perf_probe(BINARY, run.config.cases()[0], ROOT / "build")
        self.assertFalse(probe["available"])
        self.assertIn("unavailable", probe["reason"])
        output = report(run)
        self.assertIn("Sample SD/s", output)
        self.assertIn("2,000.0", output)
        self.assertIn("No steady-state or latency", output)
