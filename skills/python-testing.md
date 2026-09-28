---
name: python-testing
description: Practical pytest patterns — targeted runs, AAA structure, fixtures, regression tests
---
# Python Testing

## Running tests (targeted, never blanket)
```bash
pytest tests/test_foo.py::test_bar -x -q     # single test, stop at first failure
pytest tests/test_foo.py -k "edge" -q        # match by keyword
pytest --tb=short -q                          # readable tracebacks
```
Read the failure output fully before changing code. The assertion IS the spec.

## Writing tests
- **Arrange–Act–Assert**: build inputs, call the thing, assert on observable behavior — not implementation details.
- One behavior per test. Name it after the behavior: `test_read_file_pages_large_files`, not `test_read`.
- **Regression rule**: every bug fix ships with a test that fails without the fix.
- Fixtures for setup you reuse; never copy-paste 20 lines of setup across tests.
- Mock only true externals (network, clock, filesystem where needed). Over-mocked tests verify the mock, not the code.

## Red flags in your own tests
- A test that can't fail (asserts a constant).
- Tests coupled to error message strings that will be reworded.
- Snapshot tests of things that change intentionally.

## Before claiming done
Run the full suite once, not just the new tests — report the real summary line (`N passed, M failed`).
