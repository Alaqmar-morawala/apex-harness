---
name: security-recon
description: Authorized bug-bounty recon methodology — scope first, passive before active, evidence always
---
# Security Recon (Authorized Testing Only)

**Scope gate — before ANY active probing:** read the program's in-scope/out-of-scope list. If a target is not explicitly in scope, do not touch it. No exceptions. If scope is unclear, ask the operator.

## Phase 1 — Passive (never touches the target)
- Certificate transparency (crt.sh), search-engine dorks, Wayback, public datasets.
- ASN/WHOIS, subdomain listing from passive sources, GitHub/org disclosure recon.
- Build the asset inventory in a notes file: domain, source, first-seen date.

## Phase 2 — Fingerprinting (light touch)
- Resolve + probe for live hosts (HTTP/S), identify tech stacks (headers, favicon hashes, well-known paths).
- Rate-limit yourself: sequential, throttled requests. No aggressive crawling.

## Phase 3 — Enumeration (scoped, controlled)
- Subdomain permutation + resolution on in-scope roots only.
- Port scan only hosts you're authorized for, with sane timing (`-T2`-style).
- Directory brute-force only where the program allows it.

## Discipline
- Log every command and finding with timestamps — findings without evidence are guesses.
- Stop-and-report threshold: anything that looks like real damage (data exposure, service degradation) gets reported, not exploited further.
- Do not test: third-party embeds, out-of-scope subdomains inherited via wildcard, or anything the program excluded.

## Deliverable
A findings file per target: asset → vulnerability → evidence (request/response) → impact → remediation. No speculative severity inflation.
