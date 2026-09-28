---
name: systematic-debugging
description: Four-phase root-cause debugging — investigate before fixing; symptom fixes are failure; use for any bug, crash, or wrong behavior
---
# Systematic Debugging

**The Iron Law: NO FIXES WITHOUT ROOT-CAUSE INVESTIGATION FIRST.**
Phase 1 must be complete before you propose any fix. A symptom fix is a failed fix.

## Phase 1 — Root-cause investigation
- Read the FULL error and stack trace (bottom-up). Quote the real error in your first diagnosis line.
- Reproduce it reliably with the smallest command. If you can't reproduce, gather data — don't guess.
- Check what changed: recent diff, new dependencies, config, environment.
- Trace bad values backward to their source. **Fix at source, not at symptom.**

## Phase 2 — Pattern analysis
- Find similar WORKING code in this codebase — use the grep tool for it, don't guess from memory.
- Read the working implementation fully (page through with read_file offset/limit).
- List every difference between working and broken paths: code, config, assumptions.

## Phase 3 — Hypothesis and minimal test
- One specific hypothesis: "X is the root cause because Y."
- Smallest possible change, one variable at a time, verified with a fresh bash run.
- Hypothesis failed? Form a new one — never stack unverified fixes on top of each other.
- "I don't understand X" is a valid finding; say so instead of improvising.

## Phase 4 — Implement
- Write the failing test first (see the test-driven-development skill), then ONE fix for the root cause. No drive-by refactoring.
- Verify with the verification-before-completion skill.
- If the fix fails: under 3 attempts, return to Phase 1. At 3+, STOP — repeated failures surfacing new coupling in different places mean it's an architecture problem, not a bad hypothesis.

## Red flags — STOP and return to Phase 1
"Quick fix for now" · "let me just try changing X" · "probably the cache" · stacking a second change before verifying the first.

Adapted from obra/superpowers (MIT).
