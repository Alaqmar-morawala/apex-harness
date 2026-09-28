---
name: git-workflow
description: Clean git workflow — reviewing diffs, atomic commits, conventional messages, safe history
---
# Git Workflow

Follow this whenever the task involves commits, branches, or history surgery.

## Before committing
1. Run `git status` and `git diff` (or `git diff --staged`). Read the actual diff — never commit blind.
2. Group changes into **atomic commits**: one logical change per commit. Unrelated edits go in separate commits.
3. Never commit: secrets, cookies, tokens, `.env`, build artifacts, `node_modules`, large binaries the repo doesn't already track.

## Commit messages (conventional style)
```
<type>: <imperative summary, max ~72 chars>

<optional body explaining WHY, wrapped at 72 chars>
```
Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`.
Good: `fix: cap read_file window to stop context blowouts`
Bad: `updates` / `fixed stuff` / `WIP`.

## Branches
- Feature branches: `feat/<short-name>` or `fix/<short-name>`.
- Never force-push shared branches. Rebase your own branches only.
- When a task says "commit", commit exactly what was asked — nothing extra.

## Verification before claiming done
Run the checks the repo already has (tests/linters) and report their real output. If a check fails, fix it or say so — never report success over a red build.
