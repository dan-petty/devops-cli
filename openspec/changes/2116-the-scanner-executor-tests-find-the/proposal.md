# Proposal

## Why

#2116: the autouse fixture `scanners_installed` in `tests/security/test_scanner_tool_executor.py` makes the review scanners look installed. It patches `shutil.which`. `docs/TESTING.md` says that a test doubles only process edges, through the shared fakes. Since #1982, `scanner_fake` puts an executable stand-in for each recorded scanner first on PATH and patches no `shutil` or `subprocess` name. This file must find its scanners the same way.

## What Changes

- The fixture `scanners_installed` in `tests/security/test_scanner_tool_executor.py` writes one executable stand-in file for each tool of `_REVIEW_SCANS` into a directory under `tmp_path`. It puts that directory first on PATH with `monkeypatch.setenv`. It patches no `shutil` name.
- The imports `shutil` and `typing.Any` leave the file, because only the old fixture used them. The import `os` joins it.
- The change has no spec delta, and `.openspec.yaml` sets `skip_specs: true`. It changes a test fixture only. No `devops` command, option, message, manifest or service behavior changes, so no consumer sees it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Acceptance

- Criterion 1 (the fixture `scanners_installed` no longer patches `shutil.which`): group 1.
- Criterion 2 (the scanners are findable through executable stand-in files on PATH): group 1.
- Criterion 3 (no test in the file patches a `shutil` or `subprocess` name): group 1.

## Existing Code

- `tests/support/fakes/scanners.py`: `ScannerFake.script` (lines 206 to 213) writes the stand-in `_STAND_IN` into `bin_dir` and sets mode `0o755`. The fixture uses the same mechanism. It does not import `_STAND_IN`, which is a private name of that module, and nothing runs the stand-in of this file, so a one-line script is enough.
- `tests/security/test_scanner_tool_executor.py`: `_REVIEW_SCANS` lists the nine tools that the fixture must make findable. The 54 tests of the file, among them `test_a_review_starts_every_analyzer_through_its_executor`, keep passing.
- `src/devops_cli/review/canary.py`: `resolve_tool_binary` finds a tool with `shutil.which`, and then reads the file it found to take its digest. A stand-in on PATH is a real file, so this works.
- `docs/TESTING.md`, section "Floor and ratchets": a test doubles only edges, and a patch aimed at a stdlib name is a fallback only.

## Impact

- Tests: `tests/security/test_scanner_tool_executor.py`.
- `tests/security/test_review_tool_runs.py` holds a second `scanners_installed` fixture with the same body (line 75). Issue #2116 names one file, so this change leaves it. The follow-up is under "Workflow follow-up" in `tasks.md`.

## Feasibility

Checked on `origin/main` (4734035c) on 2026-11-01.

- The file sits in the mirror directory `tests/security/`, and the root of `tests/` holds no file of that name: `git ls-files tests | grep -c test_scanner_tool_executor` prints `1`. `git log --oneline -3 -- tests/security/test_scanner_tool_executor.py` prints `a3614198`, `95804c6d` and `513bb31f`, and the last one moved the file into the mirror directory. No newer commit touches the fixture.
- The premise holds. `git grep -n shutil -- tests/security/test_scanner_tool_executor.py` prints line 12 (`import shutil`), line 79 (`real_which = shutil.which`) and line 85 (`monkeypatch.setattr(shutil, "which", which)`). The word `subprocess` does not occur in the file.
- The fixture is needed, and it is not dead code. With the `autouse` mark removed (checked in a worktree, then restored), `uv run devops ci test tests/security/test_scanner_tool_executor.py` gives `1 failed, 53 passed, 1 error`. The failure is `host path reached without a fake: .../tools/kube-linter/0.8.3/kube-linter`. So a tool must be findable on PATH.
- The stand-in approach works. With the fixture written as the plan says (a `scanner-bin` directory under `tmp_path`, one `#!/bin/sh` file with mode `0o755` for each tool of `_REVIEW_SCANS`, and `PATH` set to that directory plus the old PATH), the same command gives `54 passed`.
- `scanner_fake` itself does not fit. With `scanners_installed` rewritten to call `scanner_fake.script(tool, ToolAnswer())` for each missing tool, the run fails with `assert ('ran', [], False) == ('coverage_gap', [], True)`, because `scanner_fake` replaces `DirectToolExecutor.run` and the PATH. This is why the design uses stand-ins of its own.
- `git grep -n scanners_installed -- tests` prints the two files named above. No open issue covers the second one: a search of the issues for `scanners_installed` finds #2116 only.
- Nothing newer did or removed the work. No newer plan or issue names this fixture. The code that looks a tool up is `resolve_tool_binary` in `src/devops_cli/review/canary.py` (line 483, `shutil.which(bin_name)`), which the stand-ins satisfy.

## Existing Tool Considered

No external tool is needed. The stand-in-on-PATH mechanism already exists in `tests/support/fakes/scanners.py` (`ScannerFake.script`), and this change applies it in the fixture of one test file. The change deletes the `shutil.which` patch and the imports that only it used.
