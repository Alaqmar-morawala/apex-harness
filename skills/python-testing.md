---
name: python-testing
description: Practical pytest patterns — targeted runs, real failure reading, regression tests; pairs with test-driven-development
---
# Python Testing

## Running tests (targeted, never blanket)
```bash
pytest tests/test_foo.py::test_bar -x -q     # single test, stop at first failure
pytest tests/test_foo.py -k "edge" -q        # match by keyword
pytest --tb=short -q                          # readable tracebacks
```
Read the failure output FULLY before changing code. The assertion is the spec.

## Writing tests
- **Arrange–Act–Assert**: build inputs, call the thing, assert observable behavior — not implementation details.
- One behavior per test. Named after the behavior: `test_read_file_pages_large_files`, not `test_read`.
- **Regression rule**: every bug fix ships with a test that fails without the fix (red-green — see the test-driven-development skill).
- Fixtures for shared setup; never copy-paste 20 lines of setup across tests.
- Mock only true externals (network, clock, filesystem edges). Over-mocked tests verify the mock, not the code.

## Red flags in your own tests
- A test that can't fail (asserts a constant).
- Coupled to error-message strings that will be reworded.
- Snapshot tests of things that change intentionally.

## Before claiming done
Run the FULL suite once, not just the new tests. Report the real summary line — `N passed, M failed` — per verification-before-completion.

Adapted in part from obra/superpowers (MIT, test-driven-development).

