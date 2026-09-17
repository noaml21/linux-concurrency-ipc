# V3 verified implementation checkpoint

Base: `8ba3536` (V2); remote main `e245d01` is its ancestor. Main does not
contain V2. V3 PR must include V2 and link a separate V2-to-V3 comparison.
Worktree: `/home/noam/Projects/linux-concurrency-ipc-v3`.
Branch: `v3/reliable-ipc-lab`. Never merge or release.

## Milestones

0. Baseline: C `make test app release` passed. Initial Python run failed only
   because Textual was absent. Installed pinned requirements in local `.venv`;
   all 34 Python/UI tests passed; legacy shm-ring CLI passed. GitHub authenticated push permission verified.
1. Reliability: pending. Extend existing engine with scoped lifecycle tracking,
   cooperative deadlines and bounded escalation; fault injection only in test build.
2. Measurement/history: pending. Bounded seeded matrices, warmups, provenance,
   per-attempt durable checkpoints, explicit V2 history compatibility.
3. Optimization: pending. Measure baseline, add bounded batched ring, compare.
4. CI/docs/review: pending. Compiler/sanitizer jobs, real report, demo, study guide,
   exact-final-commit checks, push V3 only and create one draft PR to main.

## Resume

Read this file, `AGENTS.md`, and the full user task at
`/home/noam/Documents/Codex/2026-09-17/th/outputs/V3_TASK.md`.
Inspect `git status`, log and actual verification results before continuing.
All source/documentation is English; user progress/handoff is Hebrew.
No existing C/Python tests may be weakened. SIGKILL/machine-failure limitations
must be explicit. Preserve original V1 datasets and V2 checkout.
