---
name: writing-docs
description: Focused technical documentation — one purpose per file, current truth only, no doc sprawl
---
# Writing Documentation

## Anti-sprawl rules (these exist because of real failures)
- ONE purpose per file. If you can't state the purpose in a single sentence, split or merge.
- Never create: INDEX-of-indexes, "documentation about the documentation", duplicate READMEs, or "summary" copies of files that already exist.
- Before creating a new doc, check whether an existing one should be extended instead.

## Structure
1. **Title + one-sentence purpose** at the top.
2. **Current state only** — describe how it works NOW. History belongs in git history or explicitly dated sections.
3. **Facts that change (counts, versions, paths) either live in one place or are computed** — never copy the same stat into multiple docs.
4. Concrete over abstract: real commands, real file paths, real examples that run.

## Style
- Short declarative sentences. Present tense.
- Code blocks for anything runnable; specify the shell they run in.
- Every claim a reader could verify should be verifiable in one step.

## Before finishing
Re-read the doc once asking: "could a new engineer act on this without asking a question?" If any section needs a follow-up question, it's incomplete.
