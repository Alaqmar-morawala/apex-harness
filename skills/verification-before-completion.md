---
name: verification-before-completion
description: Evidence before claims — run fresh verification before saying done/works/fixed; use before finishing ANY task or making any success claim
---
# Verification Before Completion

**Evidence before claims, always.**
**The Iron Law: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**
You may only claim a check passes if you ran the verification command in THIS task, and can quote its output.

## The gate function (in order — skipping any step is lying, not verifying)
1. **IDENTIFY** — which exact command proves this claim?
2. **RUN** — execute it fresh and complete via the bash tool.
3. **READ** — the full output, the exit code, the failure count.
4. **VERIFY** — does the output actually confirm the claim? If not, state the real status with evidence.
5. **ONLY THEN** — make the claim.

## Claim → required evidence
| Claim | Required | Not sufficient |
|---|---|---|
| Tests pass | Fresh run, 0 failures, quote the summary line | "should pass", a prior run |
| Bug fixed | The original symptom's repro now passes | "code changed" |
| File correct | read_file of the written file | the write_file success message |
| Build/runs | Exit 0 observed | linter clean, "looks fine" |
| Requirements met | Line-by-line checklist against the request | "all done" |

In Apex specifically: verifying a write_file means a read_file of that path; verifying behavior means running the program via bash — in THIS task, not the last one.

## Red flags — STOP
- Hedging: "should", "probably", "seems to".
- Satisfaction before evidence: "Great!", "Done!", "Perfect!".
- Committing/pushing without verification.
- Saying a task succeeded while any verification in it failed and wasn't re-run.

## Rationalizations, rejected
"Should work now" → run it. "I'm confident" → confidence ≠ evidence. "Just this once" → that's the time it breaks. "The write succeeded" → a successful write doesn't prove correct content.

Adapted from obra/superpowers (MIT).
