---
name: git-workflow
description: Clean git workflow — review diffs, atomic conventional commits, branch hygiene, never commit secrets
---
# Git Workflow

Follow this whenever the task involves commits, branches, or history surgery.

## Before committing
1. `git status` and `git diff` (or `git diff --staged`). Read the ACTUAL diff — never commit blind.
2. Group changes into **atomic commits**: one logical change each. Unrelated edits are separate commits.
3. Never commit: secrets, cookies, tokens, `.env`, build artifacts, `node_modules`, big binaries.

## Commit messages (conventional style)
```
<type>: <imperative summary, ~72 chars max>

<optional body: WHY, wrapped at 72>
```
Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`.
Good: `fix: cap read_file window to stop context blowouts`. Bad: `updates`, `WIP`.

## Branch hygiene
- Feature branches: `feat/<short-name>` / `fix/<short-name>`. Never force-push shared branches.
- When the task says "commit", commit exactly what was asked — nothing extra, no unsolicited README/docs churn.

## Before claiming the branch is done
- Fresh verification ran clean (see verification-before-completion): tests/build quoted with real output.
- Working tree contains only intended changes (`git status` quoted).
- Merge/PR/keep/discard is the user's call unless the task explicitly said otherwise; if merging, delete the merged branch and confirm the tree state after.

Adapted in part from obra/superpowers (MIT, finishing-a-development-branch).
