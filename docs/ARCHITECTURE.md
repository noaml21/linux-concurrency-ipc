# Architecture

The project has two layers with a strict division of responsibility:

- The **C engine** (`src/`, `include/`) performs every benchmark operation. It
  creates workers, measures elapsed time, validates every record and releases
  its own processes and IPC resources.
- The **Python lab** (`ipc_lab/`) configures and schedules engine runs, parses
  the engine's machine-readable output, computes descriptive statistics, stores
  history and renders the Textual interface. It implements no IPC or
  synchronization algorithm.

```text
 Textual UI (ipc_lab/app.py)        headless matrices (python -m ipc_lab.experiment)
              │                                   │
              └───────────────┬───────────────────┘
                              ▼
   Python orchestration: validate config → spawn engine without a shell
   → parse key=value output → statistics → JSON history / CSV / Markdown
                              │
                              ▼
   C engine (build/linux-concurrency-ipc-release, one experiment per process)
   workers · CLOCK_MONOTONIC timing · record validation · deadlines · cleanup
                              │
                              ▼
   Linux / POSIX: fork, pthreads, pipe, FIFO, System V semaphores + shared memory
```

Lifecycle, cancellation and cleanup guarantees are described separately in
[Reliability](RELIABILITY.md).

## C engine

```text
src/
├── main.c               CLI parsing and dispatch; one key=value result line
├── common/
│   ├── record.c         deterministic integrity records
│   ├── validator.c      streaming missing/duplicate/corruption checks
│   ├── io.c             partial-I/O and EINTR-safe reads/writes
│   ├── timing.c         CLOCK_MONOTONIC helpers
│   └── runtime.c        deadlines, cancellation, tracked children, reaping
├── sync/
│   ├── process_unsafe.c intentionally racy shared counter
│   ├── threads_mutex.c  pthread mutex counter
│   └── processes_sem.c  System V semaphore counter across processes
└── ipc/
    ├── pipe.c           anonymous pipe
    ├── fifo.c           named FIFO
    ├── shm_mailbox.c    capacity-1 System V shared-memory mailbox
    └── shm_ring.c       bounded ring buffer and producer-batched ring
```

The synchronization experiments increment one shared counter from several
workers. The IPC experiments use multiple producer processes and one consumer
process to transport deterministic records.

### Records and streaming validation

Each producer emits records identified by a producer ID and sequence number.
`record_make()` derives a deterministic integrity value from those fields,
allowing the consumer to detect data corruption without storing a reference copy
of every record.

The streaming validator tracks expected, received and unique records and reports
missing, duplicate, corrupted and out-of-range records. It uses one byte of
tracking state per expected record. IPC infrastructure success and record
validation are deliberately separate: a transport can complete successfully
while still reporting `validation_pass=0` if its data is incorrect.

### I/O, timing and resource handling

The common I/O layer handles partial reads and writes, retries operations
interrupted by `EINTR`, and distinguishes a complete object, clean EOF before an
object, and a partial-object/error condition. Records sent through pipes and
FIFOs are compile-time checked to fit within `PIPE_BUF`, preserving atomic
writes between producers.

Elapsed time is measured with `clock_gettime(CLOCK_MONOTONIC)`. Process and
System V IPC paths explicitly create, close, detach, reap, remove and free their
resources on success and failure paths. Semaphore-based producer/consumer modes
block in the kernel rather than busy-waiting.

The `process-unsafe` synchronization mode is intentionally different: each child
performs an unsynchronized read-modify-write on one shared counter. Lost updates
are a valid outcome and make this mode a race-condition baseline, not a correct
synchronization strategy.

### CLI contract

Successful commands print exactly one machine-readable line of
whitespace-separated `key=value` fields. Synchronization output includes expected
and observed operations, lost updates, elapsed time and operations per second.
IPC output includes validation counters, elapsed time and records per second;
ring output also includes capacity, and batch mode additionally includes
`batch_size`. A validation failure returns nonzero. See [Usage](USAGE.md#c-engine-cli)
for the command forms.

## Bounded shared-memory ring buffer

The main IPC component is a bounded, multi-producer, single-consumer ring in a
System V shared-memory segment. The shared layout contains wrapped `head` and
`tail` indices followed by a capacity-sized array of message slots.

Messages have two types:

- `RING_RECORD` carries one `record_t`;
- `RING_DONE` carries the ID of a producer that has completed.

The semaphore set contains exactly three semaphores:

- `EMPTY`: number of slots available to producers;
- `FULL`: number of messages available to the consumer;
- `PRODUCER_MUTEX`: serializes producer writes and updates to `tail`.

```text
Producer:
  wait(EMPTY)
  wait(PRODUCER_MUTEX) -> slots[tail] = message -> tail = next(tail)
  post(PRODUCER_MUTEX)
  post(FULL)

Shared memory:
  +--------+--------+-----------------------------------+
  |  head  |  tail  | slots[0] ... slots[capacity - 1] |
  +--------+--------+-----------------------------------+

Consumer:
  wait(FULL) -> message = slots[head] -> head = next(head)
  post(EMPTY)
```

Producers wait for `EMPTY` before taking `PRODUCER_MUTEX`, so they never hold the
mutex while blocked for capacity. Only producers need the mutex: several
producers share `tail`, while the single consumer exclusively updates `head`.
Both indices wrap to zero at the configured capacity instead of growing
indefinitely.

`EMPTY` and `FULL` provide bounded backpressure and transfer ownership of
individual slots between producers and the consumer. A capacity of 1 reduces the
protocol to mailbox-like behavior. Each producer sends one DONE message after its
records; the consumer terminates only after receiving one valid, non-duplicate
DONE from every producer.

The consumer waits for `FULL` with `semtimedop()` and a 100 ms timeout. On a
timeout it checks child status with non-blocking `waitpid()`. If a producer
failed, the semaphore set is removed before remaining children are reaped, waking
producers blocked in semaphore operations instead of allowing an indefinite wait.

### Producer-batched ring

`shm-ring-batch` keeps the consumer, validation, DONE handling and cleanup of the
baseline ring but replaces the producer send path. Each batch atomically reserves
N `EMPTY` slots together with the producer mutex in a single `semtimedop`, fills
the slots, then atomically unlocks and publishes N `FULL` credits. Producer
semaphore calls fall from four per record to two per batch. This is batching, not
a lock-free algorithm; the baseline remains available for comparison. Invariants,
failure handling and batch-size semantics are in
[Reliability → Batched ring](RELIABILITY.md#batched-ring); measurements are in the
[performance report](PERFORMANCE_REPORT.md).

## Python lab

```text
scripts/explore → ipc_lab/__main__.py → app.py + lab.tcss
                                         ↓
models.py → runner.py → existing C release CLI → parsing.py
                 ↓                                  ↓
             records.py ←────────────────────── analysis.py
                 ↓                                  ↓
             storage.py                       presentation.py
        results/lab/*.json                    Textual dashboard
        results/lab/exports/*.csv
```

`models.py` validates immutable configurations and expands cases, allowing future
sweep dimensions without adding benchmark logic to the UI. `runner.py` constructs
explicit argument lists and uses `asyncio.create_subprocess_exec` without a shell.
Only the C engine measures time, performs operations and validates records.
`parsing.py` checks its complete key=value contract and workload metadata;
`analysis.py` computes descriptive statistics. `experiment.py` runs bounded
headless matrices through the same runner and history as the UI. The UI renders
results and handles interaction.

### Stored data and history

Run JSON uses **schema 2**, with full configuration/schedule seed, run state, raw
stdout/stderr, exact command, wall time, correctness, engine digest, source
commit/dirty state, compiler/flags, build commit/dirty state and OS/CPU/affinity.
A matching binary digest is required before trusting its build manifest. Unknown
build metadata is labeled unavailable. Schema-1 V2 history is migrated on read
with ordered scheduling; old files are not automatically rewritten. A batch case
also records its effective batch size. Results and schedule are validated on load.

History is saved before starting, after every completed attempt and at
completion. Writes fsync a temporary sibling, atomically replace the destination
and fsync the directory. An interrupted run reopens as INCOMPLETE with prior
completed samples; the active unfinished case is not a measurement. Save failures
are shown and results retained in memory for retry. `.venv/` and `results/lab/`
are Git-ignored.

To reproduce a saved experiment, use its configuration in Configure and compare
the recorded engine digest and environment metadata. Preserve the JSON alongside
its exported CSV: the JSON contains the raw evidence and system metadata. The
original `results/benchmark_raw.csv`, `results/benchmark_summary.csv` and
`scripts/benchmark.py` are independent of the lab and retain their V1 format.
