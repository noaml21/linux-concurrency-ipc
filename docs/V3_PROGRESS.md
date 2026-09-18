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
   medians were higher, cap-2 results mixed. Final clean-build dataset completed; see V3_PERFORMANCE.md.
4. CI/docs/review: local implementation/report VERIFIED. Compiler/sanitizer jobs,
   design, real report, demo and study guide complete. Exact-final-commit checks,
   push V3 only, draft PR and remote CI inspection remain before handoff.

## Resume

Read this file, `AGENTS.md`, and the full user task at
`/home/noam/Documents/Codex/2026-09-17/th/outputs/V3_TASK.md`.
Inspect `git status`, log and actual verification results before continuing.
All source/documentation is English; user progress/handoff is Hebrew.
No existing C/Python tests may be weakened. SIGKILL/machine-failure limitations
must be explicit. Preserve original V1 datasets and V2 checkout.

## Final review checkpoint

- Added Linux GCC/Clang compiler, fault/stress, ASan/UBSan and Python/UI CI jobs.
- Focused review fixed invalid-FD polling and preservation of the deadline reason
  when a blocked worker notices expiry before the owner wakes. The first strict
  deadline-diagnostic run exposed the latter race; repaired without weakening it.
- `make test app release fault-test` passed; `make sanitizer-test` passed on GCC.
  Full 40-test suite passed before two new provenance/perf tests; all 8 targeted
  V3 tests then passed (42 total tests now). Clang unavailable locally; CI pending.
- README, resource/protocol design, five-minute demo and AI-transparent study guide
  updated. V1 raw/summary CSVs and V1 benchmark/stress scripts have no diff.
- Remaining: clean-commit measurement/report, final exact-commit full verification,
  push only V3, one draft PR, inspect/fix remote CI. Do not report completion yet.


## Resumption verification and final measurements

- Resumed without changing prior work: clean `46e479a`, original V2 PR #1 still
  untouched; remote V3 branch did not yet exist. Read task/instructions again.
- The interrupted clean verification had finished: `make clean`, `make test`,
  `make release`, all 11 stress cases PASS, and all 42 Python/UI tests PASS
  (`build/clean-python.log`, 46.078 seconds). No need to repeat those for measurement.
- Clean source/build `46e479a2de040afe15fb0e8029264b105bae3c85` measured with seed
  2026, 16 cases, 1 warmup + 4 measured repetitions = 80 successful executions.
  Data: `docs/data/v3-comparison.json` and CSV; report: `docs/V3_PERFORMANCE.md`.
  Effective batch 8 at capacity 64: median ratios 1.83..3.08; capacity 2: 0.85..1.04.
  Both source/build dirty flags false. perf remained unavailable; diagnostics saved.
- Next: commit report/checkpoint, verify exact resulting HEAD with clean C/release,
  stress, fault, sanitizer and all Python/UI tests plus launcher/CLI. Push explicitly
  `git push -u origin HEAD:refs/heads/v3/reliable-ipc-lab`. Create one DRAFT PR to main,
  explaining V2 inclusion and linking V2-to-V3 diff; inspect/fix all CI. Record final
  exact-HEAD outcomes in the PR/handoff. No merge, tag or release.
