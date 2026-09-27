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
4. CI/docs/review: VERIFIED at `ae4515e`. Full local clean verification and all
   five GitHub jobs passed for both push and PR events. Draft PR #2 exists; V2
   PR #1 is untouched. This final checkpoint update changes documentation only.
   Exact latest-HEAD verification results are maintained in the PR (see below).

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
- This earlier review checkpoint was completed by the measurement and handoff
  verification recorded below; no implementation work remains from that list.


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
- Report/data committed as `ae4515ee45e38076ec9279c0f0c8f11eeb4efac2`.
  Full exact-commit local verification passed: `make clean`, `make test app release`
  (13 C binaries), all 11 stress cases, `make fault-test` (4 methods / 54 scenarios),
  all 42 Python/UI tests (47.738 seconds), launcher + legacy/batch CLI checks,
  `make sanitizer-test` (12 safe-mode C binaries, GCC ASan/UBSan), diff checks.
- Pushed only V3 and opened [draft PR #2](https://github.com/noaml21/linux-concurrency-ipc/pull/2)
  targeting main. Existing V2 PR #1 and original V2 worktree remain unchanged.
- Inspected successful GitHub runs on `ae4515e`:
  [push](https://github.com/noaml21/linux-concurrency-ipc/actions/runs/35327963459),
  [PR](https://github.com/noaml21/linux-concurrency-ipc/actions/runs/35327964457).
  Both passed GCC/Clang build+fault+stress, GCC/Clang ASan+UBSan, and Python/UI.
  No CI failure or skipped/unavailable CI job was observed. Local Clang was absent;
  remote Clang verification is real and passed.

## Draft handoff and exact-HEAD verification

- [Branch](https://github.com/noaml21/linux-concurrency-ipc/tree/v3/reliable-ipc-lab)
- [Draft PR and latest verification record](https://github.com/noaml21/linux-concurrency-ipc/pull/2)
- [V3-only diff](https://github.com/noaml21/linux-concurrency-ipc/compare/v2/interactive-benchmark-lab...v3/reliable-ipc-lab)

The PR includes V2 because main still lacks it. Do not merge, enable auto-merge,
modify V2/main, tag or release. Performance and cleanup limitations are documented
in V3_PERFORMANCE.md and V3_DESIGN.md; perf was unavailable, not fabricated.

This checkpoint-only commit must also receive exact-HEAD verification before the
final response. Its results are recorded in the PR rather than making another
self-changing checkpoint commit. If interrupted, read `git status`, current HEAD,
`build/verified-commit.txt`, `build/final-verification.log`, and the PR head/checks.
Do not rerun completed engineering. If the log matches HEAD and all latest-HEAD CI
checks succeeded, the authorized task is complete at the draft PR handoff.
Otherwise finish only the missing checks, fix concrete failures, and update PR #2.

Verification command sequence (from this worktree):

```sh
make clean
make test app release
python3 scripts/stress.py
make fault-test
.venv/bin/python -m unittest discover -s tests/lab -v
./scripts/explore --check
make sanitizer-test
git diff --check
```

Keep the final commit's local logs under ignored `build/`; PR body working copy is
`results/lab/v3-pr-body.md`. If another push is necessary, use only
`git push origin HEAD:refs/heads/v3/reliable-ipc-lab`. Inspect both push and PR checks
for the latest head. Final user handoff remains Hebrew with branch/PR/commit links,
actual tests/CI, measured conclusions, limitations and local demo commands.
