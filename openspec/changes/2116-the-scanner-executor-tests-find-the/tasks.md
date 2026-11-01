# Tasks

## 1. Replace shutil.which patch with PATH stand-ins

Reads: none. Changes: `tests/test_scanner_tool_executor.py`.

- [ ] 1.1 Write a test that asserts the fixture creates an executable file in a directory on PATH and does not patch shutil.which. The test fails with the old fixture (which patches shutil.which) and passes with the new one (which creates a file on PATH), and verify that `uv run pytest tests/test_scanner_tool_executor.py -x` fails on the base
- [ ] 1.2 Rewrite the scanners_installed fixture. Remove the monkeypatch.setattr call on shutil.which. Instead, create a bin_dir under tmp_path, write an executable stand-in file for each scanner name the test needs, set the executable bit on each file, and prepend bin_dir to PATH with monkeypatch.setenv. Remove the shutil import if no other code in the file uses it, and verify that `uv run pytest tests/test_scanner_tool_executor.py -x` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
