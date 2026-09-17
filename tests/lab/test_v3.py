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
        task = asyncio.create_task(run_experiment(config, BINARY, cancel))
        await asyncio.sleep(0.1)
        cancel.set()
        run = await asyncio.wait_for(task, 3)
        self.assertEqual(run.status, "CANCELLED")
        self.assertEqual(len(run.attempts), 1)
        self.assertIsNone(run.attempts[0].measurement)
