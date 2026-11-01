# Proposal

## Why

#2116: tests/test_scanner_tool_executor.py has an autouse fixture scanners_installed that patches shutil.which. docs/TESTING.md says tests double only process edges through shared fakes. Since #1982, scanner_fake puts an executable stand-in for each recorded scanner first on PATH and patches no shutil or subprocess name. The fixture in this file violates that convention.

## What Changes

- Replace the scanners_installed fixture in tests/test_scanner_tool_executor.py to create executable stand-in files in a temp directory and prepend that directory to PATH, instead of patching shutil.which.
- Remove the shutil import if it is no longer used in the file.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-runs`: test-fixture-makes-scanner-findable-on-path

## Impact

- Tests: `tests/test_scanner_tool_executor.py`

## Feasibility

- The premise is confirmed: tests/test_scanner_tool_executor.py:77 defines def scanners_installed(monkeypatch: pytest.MonkeyPatch) -> None: which patches shutil.which, as cited in the issue body and in openspec/changes/archive/2026-10-24-1982-scanner-fake-through-tool-executor/tasks.md:23.
- The stand-in-on-PATH pattern is established in tests/support/fakes/scanners.py (ScannerFake.script writes an executable stand-in in bin_dir, and the fixture puts bin_dir first on PATH), as documented in the design of #1982.
- First check: run grep -n 'shutil.which' tests/test_scanner_tool_executor.py to confirm the patch exists before the change.
- Second check: run uv run pytest tests/test_scanner_tool_executor.py -x to confirm all tests pass after the change.
- Third check: run grep -n 'monkeypatch.setattr.*shutil\|monkeypatch.setattr.*subprocess' tests/test_scanner_tool_executor.py to confirm no shutil or subprocess name is patched.

## Existing Tool Considered

No external tool is needed. The stand-in-on-PATH pattern already exists in tests/support/fakes/scanners.py (ScannerFake.script). This change reuses the same mechanism in the test fixture. No internal code is deleted; the fixture body is rewritten in place.
