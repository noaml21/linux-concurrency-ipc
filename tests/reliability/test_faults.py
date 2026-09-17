"""Bounded tests signal only a Popen-owned parent; engine tracks/reaps its children."""
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "build/linux-concurrency-ipc-fault"
CASES = [("ipc", mode) for mode in ("pipe", "fifo", "shm-mailbox", "shm-ring")]
CASES += [("sync", mode) for mode in ("process-sem", "process-unsafe")]


def command(family, mode, amount=100, deadline=250):
    args = [str(BINARY), family, mode, "3", str(amount)]
    if mode.startswith("shm-ring"):
        args.append("2")
    if mode == "shm-ring-batch":
        args.append("2")
    return args + ["--deadline-ms", str(deadline)]


class FaultTests(unittest.TestCase):
    def assert_clean(self, stderr):
        for pid in re.findall(r"owned_pid=(\d+)", stderr):
            self.assertFalse(Path(f"/proc/{pid}").exists(), f"unreaped child {pid}")
        for kind in ("shm", "sem"):
            ids = {line.split()[1] for line in Path(f"/proc/sysvipc/{kind}").read_text().splitlines()[1:]}
            for owned in re.findall(rf"owned_{kind}=(\d+)", stderr):
                self.assertNotIn(owned, ids, f"owned {kind} leaked: {owned}")
        for fifo in re.findall(r"owned_fifo=(\S+)", stderr):
            self.assertFalse(Path(fifo).exists())
            self.assertFalse(Path(fifo).parent.exists())

    def test_fault_matrix(self):
        for family, mode in CASES:
            for fault in ("producer-fail", "producer-stall", "startup", "cancel"):
                with self.subTest(mode=mode, fault=fault):
                    start = time.monotonic()
                    result = subprocess.run(command(family, mode), text=True, capture_output=True,
                                            env={**os.environ, "IPC_LAB_TEST_FAULT": fault}, timeout=4)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertLess(time.monotonic() - start, 3)
                    self.assertFalse(result.stdout, "failed work must not become a measurement")
                    self.assert_clean(result.stderr)

    def test_backpressure_success_and_deadline(self):
        for family, mode in CASES:
            if family != "ipc":
                continue
            for amount, deadline, success in ((5, 2000, True), (1000, 100, False)):
                with self.subTest(mode=mode, success=success):
                    result = subprocess.run(command(family, mode, amount, deadline), text=True,
                                            capture_output=True, timeout=4,
                                            env={**os.environ, "IPC_LAB_TEST_FAULT": "slow-consumer"})
                    self.assertEqual(result.returncode == 0, success, result.stderr)
                    self.assert_clean(result.stderr)

    def test_parent_interrupt_reaps_stalled_children(self):
        for family, mode in CASES:
            for sig in (signal.SIGINT, signal.SIGTERM):
                with self.subTest(mode=mode, signal=sig):
                    process = subprocess.Popen(command(family, mode, deadline=5000), text=True,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               env={**os.environ, "IPC_LAB_TEST_FAULT": "producer-stall"})
                    # Wait for a trace of an owned child, not a guessed startup delay.
                    prefix = ""
                    while "owned_pid=" not in prefix:
                        line = process.stderr.readline()
                        self.assertTrue(line)
                        prefix += line
                    process.send_signal(sig)
                    stdout, stderr = process.communicate(timeout=4)
                    self.assertNotEqual(process.returncode, 0)
                    self.assertFalse(stdout)
                    self.assert_clean(prefix + stderr)

    def test_threads_deadline_and_production_fault_is_disabled(self):
        result = subprocess.run(command("sync", "threads-mutex", 1000000000, 50),
                                text=True, capture_output=True, timeout=4)
        self.assertNotEqual(result.returncode, 0)
        binary = ROOT / "build/linux-concurrency-ipc-release"
        result = subprocess.run([str(binary), "ipc", "shm-ring", "2", "10", "2"],
                                env={**os.environ, "IPC_LAB_TEST_FAULT": "producer-stall"},
                                text=True, capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("owned_", result.stderr)
