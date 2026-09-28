---
name: writing-plans
description: Turn a goal into a numbered implementation plan of small verifiable steps; use for multi-file or multi-stage work
---
# Writing Plans

A plan is a list of steps small enough that each one can be **done AND verified** in a couple of tool calls. If a step can't name its verification, it's too big — split it.

## Format (your step-1 response for planned tasks)
```
Goal: <one sentence>

1. <action> — verify: <how>
2. <action> — verify: <how>
...
```
Each step names the action AND how you'll prove it worked (a command, a read_file, a test). Then execute in order.

## Rules
- **Order by dependency**: data model before API, API before UI, failing test before fix.
- **Front-load discovery**: a "read X to confirm Y" step is a real step. Exploring before writing beats rewriting after.
- **Verification per step** comes from the verification-before-completion skill: fresh run, real output, quoted.
- **Scope lock**: the plan lists files you intend to touch. If you find yourself editing a file NOT in the plan, either it's necessary (say why, update the plan) or stop.
- Plans live in chat, not on disk (no unsolicited files).

## Adapting mid-flight
If step N's verification fails: invoke systematic-debugging — don't silently swap in a new approach. Re-plan explicitly: "step 3 failed because X; revised plan: ..." and continue.

Inspired by obra/superpowers (MIT), adapted for Apex's step-1 plan rule.
