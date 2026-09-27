"""Sequential C execution with cooperative cancellation and durable checkpoints."""

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import signal
import time
from typing import Callable

from .models import Case, Config
from .records import Attempt, Run, environment, utc_now

# Context preserves execute's V2 callable interface for clients/test doubles.
_settings: ContextVar[tuple[int, asyncio.Event | None]] = ContextVar("execution", default=(30000, None))


@dataclass(frozen=True)
class Progress:
    phase: str
    run: Run
    case: Case
    repetition: int


async def execute(binary: Path, case: Case, repetition: int) -> Attempt:
    deadline, cancel = _settings.get()
    command = (*case.command(binary), "--deadline-ms", str(deadline))
    started = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(
            *command, cwd=binary.parent.parent,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        return Attempt(case, repetition, launch_error=str(error), command=command)
    communication = asyncio.create_task(process.communicate())
    signalled = False
    try:
        while not communication.done():
            await asyncio.wait({communication}, timeout=0.025)
            if communication.done():
                break
            if cancel is not None and cancel.is_set() and not signalled:
                if process.returncode is None:
                    try:
                        process.send_signal(signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                signalled = True
            # The C owner performs normal cleanup. This is an emergency watchdog
            # for a broken/unresponsive owner; such a run is never accepted.
            if time.monotonic() - started > deadline / 1000 + 3:
                raise TimeoutError("C owner exceeded shutdown grace; cleanup not guaranteed")
        stdout, stderr = await communication
    except (asyncio.CancelledError, TimeoutError) as error:
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        try:
            stdout, stderr = await asyncio.wait_for(asyncio.shield(communication), 1)
        except asyncio.TimeoutError:
            if process.returncode is None:
                process.kill()
            stdout, stderr = await communication
        if isinstance(error, asyncio.CancelledError):
            raise
        return Attempt(case, repetition, stderr=str(error), returncode=1,
                       command=command, wall_seconds=time.monotonic() - started)
    return Attempt(case, repetition, stdout.decode("utf-8", errors="replace"),
                   stderr.decode("utf-8", errors="replace"), process.returncode,
                   command=command, wall_seconds=time.monotonic() - started)


async def run_experiment(
    config: Config,
    binary: Path,
    cancel: asyncio.Event,
    notify: Callable[[Progress], None] = lambda event: None,
    checkpoint: Callable[[Run], object] | None = None,
) -> Run:
    binary = binary.resolve()
    run = Run(config, await asyncio.to_thread(environment, binary))

    async def save() -> None:
        if checkpoint is not None:
            await asyncio.to_thread(checkpoint, run)

    await save()
    settings = _settings.set((config.deadline_ms, cancel))
    session_started = time.monotonic()
    try:
        for case, repetition in config.schedule():
            if cancel.is_set() or time.monotonic() - session_started > 600:
                cancel.set()
                break
            notify(Progress("started", run, case, repetition))
            task = asyncio.create_task(execute(binary, case, repetition))
            while True:
                try:
                    attempt = await asyncio.shield(task)
                    break
                except asyncio.CancelledError:
                    cancel.set()
                    if task.cancelled():
                        raise
            run.attempts.append(attempt)
            await save()
            notify(Progress("completed", run, case, repetition))
        run.cancelled = cancel.is_set()
        run.finished = utc_now()
        await save()
        return run
    finally:
        _settings.reset(settings)
