# V3 verified implementation checkpoint

Base: `8ba3536` (V2); remote main `e245d01` is its ancestor. Main does not
contain V2. V3 PR must include V2 and link a separate V2-to-V3 comparison.
Worktree: `/home/noam/Projects/linux-concurrency-ipc-v3`.
Branch: `v3/reliable-ipc-lab`. Never merge or release.

## Milestones

0. Baseline: C `make test app release` passed. Initial Python run failed only
   because Textual was absent. Installed pinned requirements in local `.venv`;
   all 34 Python/UI tests passed; legacy shm-ring CLI passed. GitHub authenticated push permission verified.
1. Reliability: VERIFIED. Scoped lifecycle tracking, cooperative deadlines,
   bounded escalation and test-only fault hooks implemented. `make test app release
   fault-test` passed (12 C binaries, 4 parameterized fault tests); all 10 unchanged
   V2 execution/history tests passed; legacy CLI covered; diff scope checked.
   Design/audit and exact SIGKILL/OS scheduling limitations: V3_DESIGN.md.
2. Measurement/history: VERIFIED. `make test app release` passed; all 38 Python
   tests including real UI passed; launcher passed. Real 32-execution ring matrix
   completed with 24 accepted measured samples (8 warmups). Raw development
   dataset and unavailable perf diagnostics committed; original V1 data untouched.
   Schema 1 migration, active cancellation, checkpoints and seed bounds tested.
3. Optimization: VERIFIED. Producer-batched ring implemented alongside baseline.
   `make test app release fault-test` passed, including all batch sizes through
   capacity 64, wraparound, partial batches and fault cleanup. All 40 Python/UI
   tests passed. An 80-execution development comparison completed; cap-64 batch-8
   medians were higher, cap-2 results mixed. Final clean-build dataset pending.
4. CI/docs/review: pending. Compiler/sanitizer jobs, real report, demo, study guide,
   exact-final-commit checks, push V3 only and create one draft PR to main.

## Resume

Read this file, `AGENTS.md`, and the full user task at
`/home/noam/Documents/Codex/2026-09-17/th/outputs/V3_TASK.md`.
Inspect `git status`, log and actual verification results before continuing.
All source/documentation is English; user progress/handoff is Hebrew.
No existing C/Python tests may be weakened. SIGKILL/machine-failure limitations
must be explicit. Preserve original V1 datasets and V2 checkout.
