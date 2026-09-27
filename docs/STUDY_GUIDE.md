# Interview study guide: explain this implementation

This prototype was developed with AI assistance. Treat the code, tests and raw
measurements as evidence; do not present generated development work as personal
experience you did not have. Reproduce the demo, inspect the code and make your
own explanations before discussing the project.

## Concepts covered

- Linux process creation, child reaping, and thread management
- Race conditions, read-modify-write hazards, and critical sections
- pthread mutex synchronization
- System V semaphore creation, operations, timeouts, and removal
- Anonymous pipes and named FIFOs with atomic record writes
- System V shared-memory attachment, detachment, and cleanup
- Multi-producer/single-consumer ownership-transfer protocols
- Capacity-1 mailboxes and bounded ring buffers with backpressure
- Failure-aware cleanup without busy waiting
- Deterministic integrity records and streaming correctness validation
- Strict C11 compilation, focused functional tests, stress testing, and reproducible benchmark summaries

## Walk the actual data path

Start at `src/main.c`, then `ipc_run_shm_ring` / `ipc_run_shm_ring_batch` in
`src/ipc/shm_ring.c`. Explain fork inheritance, the System V segment layout,
head/tail ownership, record generation and integrity validation. Follow the path
from a producer's EMPTY reservation to consumer FULL acquisition and EMPTY release.
Locate DONE handling and explain why each producer needs a unique completion marker.

Study `src/common/runtime.c`: one process-scoped experiment, monotonic deadline,
lock-free atomic signal flag, timed semaphore waits, exact-PID waits and escalation.
Explain why signals cannot do allocation/free/stdio cleanup in their handlers,
why an unreaped child retains its PID, and why waitpid(-1) was too broad for the API.
Understand PDEATHSIG's parent-race check and its limits for named/System V objects.

## Questions to answer with code, not slogans

- Why does EMPTY + FULL equal capacity only when no operations are in flight?
  Account for producer reservations, initialized-but-unpublished records and a
  consumer-owned slot. Show the batch invariant during a partially written batch.
- Why not hold the producer mutex while waiting for N free slots? How does the
  atomic two-action semtimedop prevent that deadlock? Which side owns head/tail?
- Does SEM_UNDO repair a half-written ring slot? Why can the counter mutex use it
  while the transport aborts on writer death? Safety and liveness are separate.
- Why can multiple pipe writers share one channel? Explain PIPE_BUF versus general
  partial writes and how truncated input differs from clean EOF. Who closes which
  descriptor, and why does FIFO startup need bootstrap descriptors?
- What happens if fork number two fails? If a producer fails after reserving? If it
  receives SIGSTOP? If the parent receives SIGTERM? What cannot be promised after
  SIGKILL or kernel uninterruptible sleep? Point to a test for each covered case.
- Why are batch size one and baseline not identical syscall paths? Count producer
  and consumer semaphore calls. Why might larger batches hurt buffering delay?
- Why is the unsafe counter's high attempted rate not useful synchronized throughput?
  Why doesn't a run with zero lost updates establish correctness?
- What exactly is timed? Separate resource setup, worker lifecycle, online validation,
  final O(1) summary, cleanup and Python wall time. Why is none of this per-record latency?
- How do seeded interleaved blocks reduce order bias without eliminating thermal,
  scheduling or system-load effects? What claims can four repetitions support?
- What does fsync + replace + directory fsync protect? What can still be lost? How
  are schema-1 history, negative warmup repetitions and INCOMPLETE snapshots handled?

## Concrete engineering findings

The original IPC engine already had working record validation and ring protocols.
V3 extends them; the main reliability gaps were unbounded retry/wait behavior and
unscoped child reaping. Polling introduced a potential invalid-descriptor regression:
poll ignores negative descriptors, so V3 explicitly rejects them and tests it.
A deadline alone would not recover a SIGSTOP child holding capacity; the controlled
stall tests require exact-child SIGKILL escalation and reaping.

The optimization batches producer reservation/publication, retaining the individual
consumer and integrity checks. Development measurements showed larger medians for
capacity 64 / batch 8 and mixed results for capacity 2. Read the final [performance
report](PERFORMANCE_REPORT.md) and raw JSON before quoting numbers. perf was unavailable under existing
kernel permissions, so no hardware-counter bottleneck claim is supported.

Tests are evidence of selected paths, not a proof of every interprocess ordering.
ASan/UBSan check memory/undefined behavior in safe-mode paths; they do not establish
interprocess synchronization correctness. There is no lock-free rewrite, latency
histogram, process recovery after arbitrary instruction failure or global scavenger.

## Hands-on exercises

Run the [five-minute demo](DEMO.md). Trace a capacity-2, batch-2, three-record producer by hand,
including its final partial batch and DONE. Read `test_shm_ring_batch.c`, change an
experiment seed and explain the changed raw schedule, then compare median and spread
without calling either a significance test. Finally, explain the tradeoff you would
measure next and what instrumentation would be required before making that claim.
