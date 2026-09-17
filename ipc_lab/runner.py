"""Sequential nonblocking execution, with resource-safe cancellation boundaries."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import Case, Config
from .records import Attempt, Run, environment, utc_now


@dataclass(frozen=True)
class Progress:
    phase: str
    run: Run
    case: Case
    repetition: int


async def execute(binary: Path, case: Case, repetition: int) -> Attempt:
    try:
        process = await asyncio.create_subprocess_exec(
            *case.command(binary), cwd=binary.parent.parent,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = await process.communicate()
    except OSError as error:
        return Attempt(case, repetition, launch_error=str(error))
    return Attempt(case, repetition, stdout.decode("utf-8", errors="replace"),
                   stderr.decode("utf-8", errors="replace"), process.returncode)


async def run_experiment(
    config: Config,
    binary: Path,
    cancel: asyncio.Event,
    notify: Callable[[Progress], None] = lambda event: None,
) -> Run:
    # Resolve once: neither mechanism names nor other UI input select an executable.
    binary = binary.resolve()
    run = Run(config, await asyncio.to_thread(environment, binary))
    for case in config.cases():
        for repetition in range(1, config.repetitions + 1):
            if cancel.is_set():
                break
            notify(Progress("started", run, case, repetition))
            task = asyncio.create_task(execute(binary, case, repetition))
            # Do not cancel communicate() or orphan the engine. It owns resource
            # cleanup. Also drain safely if the enclosing UI worker is cancelled.
            while True:
                try:
                    attempt = await asyncio.shield(task)
                    break
                except asyncio.CancelledError:
                    cancel.set()
                    if task.cancelled():
                        # Event-loop shutdown may also cancel the inner task;
                        # never spin waiting for an already-cancelled task.
                        raise
            run.attempts.append(attempt)
            notify(Progress("completed", run, case, repetition))
        if cancel.is_set():
            break
    run.cancelled = cancel.is_set()
    run.finished = utc_now()
    return run
