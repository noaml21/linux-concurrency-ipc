# Five-minute demo

A guided tour of the lab, failure handling and a reproducible comparison.
Run from the repository root. Setup ([details](USAGE.md#setup)) is outside the
five-minute budget:

```sh
make release
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lab.txt
./scripts/explore --check
```

1. **Minute 1 — valid run.** Start `./scripts/explore`, set items to 100 and
   repetitions to 1, Ctrl+R. Inspect PASS, raw counts and the saved History row.
   The four V2 modes remain selected by default; batch is opt-in.
2. **Minute 2 — capacity.** Return to Configure, select only shm-ring, enable
   Sweep and use capacities `1, 8, 64`. Run. Explain why capacity changes
   backpressure but does not change expected/received records. Inspect spread only
   after increasing repetitions; one sample cannot estimate repeatability.
3. **Minute 3 — failure and cleanup.** In another terminal:

   ```sh
   make build/linux-concurrency-ipc-fault
   IPC_LAB_TEST_FAULT=producer-stall ./build/linux-concurrency-ipc-fault ipc shm-ring-batch 3 100 2 2 --deadline-ms 250
   echo "$?"
   make fault-test
   ```

   The first command deliberately returns 1, emits owned resource/PID traces and
   `error: IPC experiment failed: deadline exceeded`. PIDs/IDs vary. It stops
   producers inside reserved slots before publishing. The owner escalates, reaps
   and cleans up. The suite verifies exact traced objects are absent across modes.
   Never substitute broad killall/ipcrm commands. Production ignores the fault flag.
4. **Minute 4 — compare.** Run a small interleaved comparison:

   ```sh
   .venv/bin/python -m ipc_lab.experiment --modes shm-ring,shm-ring-batch --workers 1,2 --amounts 2000 --capacities 2,64 --repetitions 3 --warmups 1 --batch-size 8 --seed 2026
   ```

   Open the printed JSON's sibling `.md` report. Inspect n, min/max and SD; compare
   equal workers/items/capacity only. Capacity 2 uses effective batch 2, capacity
   64 uses batch 8. The measured local report contains both gains and limitations.
5. **Minute 5 — cancellation and recovery.** In the UI choose only shm-mailbox,
   2 producers, 100000 items, 3 repetitions. Start, then Ctrl+X during execution.
   The owner returns an error for partial work; the session is CANCELLED. Export,
   reopen History, and explain why cancelled attempts do not enter rate statistics.
   Completed previous attempts remain durable; an abrupt app interruption recovers
   an INCOMPLETE snapshot. Ctrl+Q normally drains and saves before quitting.

## Actual output example

Recorded on the development i5-12450H, not an expected performance target:

```text
family=ipc mode=shm-ring-batch producers=2 records_per_producer=31 capacity=2 batch_size=2 expected=62 received=62 missing=0 duplicates=0 corrupted=0 out_of_range=0 validation_pass=1 elapsed_seconds=0.002308 records_per_second=26860.361644
```

Timing depends on machine/load. No steady-state or per-record latency instrumentation
is present. SIGKILL of the C owner or machine failure cannot guarantee named or
System V resource cleanup; these are not successful cancellation demonstrations.
