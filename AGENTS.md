# Linux Concurrency & IPC V2 Development Rules

## Mission

Build an impressive interactive benchmark lab on top of the existing
Linux Concurrency & IPC project without weakening or unnecessarily
rewriting the existing C/Linux benchmark engine.

The current V1 behavior is the stable baseline.

## Working method

- Work autonomously, but strictly milestone by milestone.
- Never start the next milestone until the current milestone passes its
  required verification.
- Inspect the existing repository before making architectural decisions.
- Prefer extending the existing interfaces over rewriting working code.
- Keep the C benchmark engine as the source of truth for benchmark data.
- Do not modify unrelated code.
- Do not weaken, delete, or bypass existing tests.
- Add tests for all new non-trivial logic.
- Prefer small, reviewable commits.
- Commit only after a milestone is verified.
- Never merge into main.
- Never force-push or rewrite Git history.
- Never use destructive Git commands such as reset --hard or clean -fd.
- Do not write outside this repository.
- Do not use sudo or make system-wide changes.

## Branch policy

All V2 work must remain on:

v2/interactive-benchmark-lab

Never switch to or modify main except to read its history.

## Verification

After every milestone:

1. Run the new feature's targeted tests.
2. Run `make test`.
3. Confirm the existing benchmark CLI still behaves correctly.
4. Inspect `git diff` for unrelated changes.

Before the final prototype is considered complete:

- `make clean`
- `make test`
- `make release`
- `python3 scripts/stress.py`
- all new Python tests
- a small real end-to-end benchmark through the interactive application

If any required verification fails, fix it before proceeding.

## Failure policy

A failing milestone may be repaired autonomously.

If the same blocking failure remains after three serious repair attempts,
stop instead of hiding, bypassing, or weakening the failing check.

If a major architectural change to the existing C engine appears necessary,
first look for a less invasive design.

## Dependencies

A small Python UI dependency is acceptable.
Prefer Textual for the terminal application.

Do not introduce a web frontend, Node.js backend, database, user accounts,
cloud services, or unrelated infrastructure.

## Product goal

The final prototype should turn the repository from a benchmark that is
mostly consumed through CLI output and README tables into an interactive
Linux systems experimentation tool.

It should remain clearly recognizable as a C/Linux systems project.
