# V3 engine reliability and measurement design

## Ownership and lifecycle

The C engine remains the only benchmark implementation. Each API executes one
experiment at a time in a process. `runtime_begin` starts a monotonic deadline;
CLI default is 30 seconds, configurable with trailing `--deadline-ms 1..120000`.
At most 64 workers are accepted by the engine (32 in the lab). This global runtime
is deliberately not a concurrently callable/reentrant library interface.

The owner allocates resources, forks tracked PIDs, consumes/joins, validates, reaps,
then removes its exact semaphore/shared-memory IDs and FIFO path. No wildcard
wait, process-group signal, or global IPC cleanup is used. An unrelated child is
covered by a C regression test. Children set Linux PDEATHSIG with a parent-race
check. Signal handlers set a lock-free atomic flag; no cleanup runs in handlers.
The CLI handles SIGINT/SIGTERM and ignores SIGPIPE so broken writes return errors.
Library callers must explicitly use `runtime_configure` to install handlers.

States: initialized -> starting -> running -> draining -> validated -> cleaned.
Any error or cancellation goes to aborting -> reaping -> cleaned, never validated.
A failed IPC validation is a nonzero CLI outcome. Successful V1 output is unchanged.

Cancellation is checked in semaphore waits (50 ms), I/O readiness (50 ms), worker
loops and child waits. Shared-memory consumers poll full slots at 100 ms and
inspect tracked exits. Failure removes the owned semaphore set to wake waiters.
Reaping sends SIGTERM to unreaped owned children, then SIGKILL after 200 ms;
SIGSTOP-injected children therefore cannot indefinitely block ordinary shutdown.
Reaping itself must still wait for the kernel: no userspace program can guarantee
a hard wall-clock bound for uninterruptible kernel sleep or an unscheduled owner.
The application deadline is a cooperative execution budget, not a real-time SLA.

SIGKILL of the owner, power loss, or kernel failure cannot guarantee System V
semaphore/shared-memory or FIFO cleanup. PDEATHSIG reduces orphaned computation
but does not reclaim named/System V resources. Never claim otherwise or remove
resources just because their owner UID matches. No persistent cleanup daemon.

## Audit and synchronization invariants

- Pipe/FIFO: fixed records fit PIPE_BUF, blocking writes preserve record atomicity.
  Common I/O handles EINTR, short reads/writes, EOF at record boundaries and rejects
  truncated records. Readiness polling permits cancellation; closing the read end
  breaks blocked writers. FIFO bootstrap descriptors prevent premature EOF during
  startup; only its mkdtemp-created directory is removed.
- Mailbox: EMPTY reserves its sole slot; producer initializes a message before
  posting FULL. Consumer copies before releasing EMPTY. RECORD and producer-specific
  DONE messages are validated. Failed in-flight reservations abort the entire run.
- Ring baseline: EMPTY reserves bounded capacity; producer mutex orders tail writes;
  FULL advertises initialized records; single consumer owns head. At rest
  EMPTY + FULL = capacity. During work, also count producer reservations, initialized
  but not yet published entries and consumer-owned slots. SEM_UNDO cannot repair a
  half-written protocol, so mailbox/ring abort rather than pretending to recover.
- process-sem: SEM_UNDO protects the shared counter mutex on child exit, but a
  failed child still invalidates the measurement. mmap belongs to this process tree.
- threads-mutex: locked increments; cooperative checks before locking, joined before
  destroying stack-owned context/mutex. Critical sections contain no blocking I/O.
  Partial thread creation requests cancellation before joining created threads.
- process-unsafe: intentionally racy demonstration, never a correctness baseline.

Safety (no invalid measurement, duplicate ownership, or buffer overwrite) is
separate from liveness (deadline detection, wakeups, escalation). No fairness or
starvation guarantee is claimed for System V semaphore scheduling.

## Fault coverage

`make fault-test` builds `IPC_TESTING` separately. Production binaries do not read
fault variables or print resource traces. `IPC_LAB_TEST_FAULT` accepts:

| Fault | pipe/FIFO | mailbox/ring | process-sem/unsafe | threads |
|---|---|---|---|---|
| producer-fail | before write | inside reservation/mutex | inside operation/lock | not injected |
| producer-stall | before write | inside reservation/mutex | inside operation/lock | not injected |
| startup | second fork fails | second fork fails | second fork fails | real error path only |
| cancel | child signals owner | child signals owner | child signals owner | deadline test |
| slow-consumer | before read | before consume | not applicable | not applicable |
| parent SIGINT/SIGTERM | stalled workers | stalled workers | stalled workers | cooperative deadline |

Tests check nonzero/error output, traced child disappearance (including zombies),
absence of exact traced IPC IDs/FIFO paths, backpressure success and deadline abort.
Faults intentionally affect every producer at its first critical operation. They
are deterministic protocol probes, not exhaustive schedule exploration. Kernel
allocation errors, arbitrary thread stalls and SIGKILL cleanup are not simulated.

## Timing

Engine `elapsed_seconds` begins immediately before worker creation and ends after
consumption and child reaping/joining. It includes record generation, transport,
online validation, scheduling, polling and lifecycle overhead. It excludes initial
resource/validator allocation, final validator scan and final resource destruction.
This is a **worker-lifecycle interval**, not steady state or full end-to-end time.
No per-record latency is instrumented. V3 cancellation checks have measurable cost;
comparisons must use the same build and validation settings.
