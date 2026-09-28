---
name: test-driven-development
description: Enforce red-green-refactor — no production code without a failing test first; use for any new feature, bug fix, or behavior change
---
# Test-Driven Development

**The Iron Law: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.**
If code was written before the test, delete it — don't keep it "as reference". Start over from the test.

Core principle: if you didn't watch the test fail, you don't know if it tests the right thing.

## The Cycle (every step runs a real command via the bash tool)

**RED** — Write ONE minimal failing test for ONE behavior. Real code over mocks; mock only true externals.
**Verify RED (mandatory, never skip)** — Run it with bash. It must FAIL, not error. The failure message must be the expected one, caused by the missing feature — not a typo or import error. If it passes immediately, you're testing existing behavior: fix the test.
**GREEN** — Write the simplest code that passes. No extra options, no "while I'm here" improvements (YAGNI).
**Verify GREEN (mandatory)** — Your test passes AND the full suite passes AND you can quote the summary line (`N passed`). If your test fails, fix the CODE, not the test.
**REFACTOR** — Only after green: remove duplication, improve names. Tests stay green. No new behavior.
Repeat with the next failing test.

## Apex execution pattern
One tool call per step: write the test (write_file) → run it (bash) → write the code (write_file/edit_file) → run again (bash) → run the full suite (bash). Each verification is a fresh bash run whose real output you quote — never "should pass now".

## Rejected rationalizations
- "Too simple to test" → then the test is 3 lines.
- "I'll add tests after" → tests written after pass immediately and prove nothing.
- "Already manually verified" → one manual run isn't comprehensive and isn't repeatable.
- "Deleting the code is wasteful" → sunk cost; the code isn't evidence.
- "TDD slows me down" → guess-and-fix loops are slower.

## When stuck
Hard to test = the design is hard to use. Excessive mocking = too much coupling — inject dependencies instead. Huge setup = extract helpers or split the unit.

Adapted from obra/superpowers (MIT).
