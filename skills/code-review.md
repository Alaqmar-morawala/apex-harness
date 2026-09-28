---
name: code-review
description: Defect-first code review checklist — correctness, edges, security, tests
---
# Code Review

Review for DEFECTS first, style last. For every finding: file, line, what breaks, why.

## Correctness
- Does the code do what it claims? Trace one happy path AND one failure path by hand.
- Off-by-one on loops/slices; wrong boundary conditions (`<` vs `<=`).
- None/undefined handling, empty collections, single-element collections.
- Error paths: are exceptions caught at the right level? Swallowed errors (`except: pass`) are findings.

## Concurrency & state
- Shared mutable state without locks.
- Calls that assume ordering across async/thread boundaries.

## Security (defensive review)
- Injection: SQL string-building, shell command interpolation, unescaped output.
- Secrets in code/logs/diffs. Path traversal on user-supplied paths.
- Unvalidated input crossing a trust boundary.

## Design
- Duplicated logic that will drift.
- Dead code, misleading names, functions doing two things.
- Missing tests for the new behavior.

## Output format
Group findings by severity: **[P0] breaks things**, **[P1] likely bugs**, **[P2] risks/tech-debt**, **[P3] nits**. One line per finding with `file:line`. No praise padding — end with a one-line overall verdict.
