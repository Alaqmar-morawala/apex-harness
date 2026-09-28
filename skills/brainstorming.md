---
name: brainstorming
description: Refine vague or high-stakes ideas into a validated design BEFORE building; use when requirements are ambiguous or the change is large
---
# Brainstorming (Design Before Code)

Use when the request is vague, has multiple plausible architectures, or is expensive to undo. Skip it for clear, small tasks — then just execute.

## Process
1. **Restate the goal** in one sentence: what does success look like?
2. **Explore the current state first** — list_dir / grep / read what exists. Don't design against an imagined codebase.
3. **Generate 2–3 genuinely different approaches** (not one approach with cosmetic variants). Note the trade-off of each: complexity, risk, blast radius, maintainability.
4. **Recommend one** and say why in one sentence.

## Deciding (Apex runs in auto-execute mode)
- Small or reversible → state the chosen design in 3–5 lines, then BUILD it. Don't stall waiting for approval.
- Large, destructive, or genuinely ambiguous (data loss, public APIs, spend) → present the options + recommendation and STOP for the user's call. That's not a stall, that's the design gate.

## Scope guard
Brainstorming output is a short design section in your plan (goal, chosen approach, why, key files touched) — NOT a design document on disk. Remember: no unsolicited files.

## Anti-patterns
- Designing in a vacuum without reading the existing code.
- Presenting one option and calling it brainstorming.
- Asking questions a quick read_file could have answered.

Inspired by obra/superpowers (MIT), adapted for an auto-executing terminal agent.
