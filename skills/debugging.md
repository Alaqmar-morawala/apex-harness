---
name: debugging
description: Systematic debugging methodology — reproduce, isolate, hypothesize, verify
---
# Debugging Methodology

Work through failures in this order. Never shotgun-fix.

## 1. Reproduce
Get the exact failure on demand with the smallest possible command. Capture the FULL error output — read the traceback bottom-up; the first line of your diagnosis should quote the real error.

## 2. Isolate
Binary-search the failure surface:
- Which component? (run the pieces separately)
- Which input? (minimize the failing case)
- Which commit? (`git bisect` if it regressed)
- Environment or code? (same code elsewhere, same env elsewhere)

## 3. Hypothesize
State the hypothesis in one sentence BEFORE changing anything:
"My hypothesis: X fails because Y." Then design the cheapest experiment that could disprove it.

## 4. One change at a time
Apply a single change, re-run the reproduction. If it didn't change the behavior, revert it before trying the next idea.

## 5. Fix root cause, not symptom
If the fix touches a symptom (a retry, a swallowed exception, a hardcoded value), stop and find the actual defect. A fix without understanding is a future bug.

## 6. Verify
- The original repro now passes.
- Add a regression test that fails without the fix.
- Run the neighboring tests — check you didn't break the edges.
