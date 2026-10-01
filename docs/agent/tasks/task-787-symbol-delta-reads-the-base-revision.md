# Task: The Symbol Delta Reads the Base Revision's File Again (#787)

**Issue**: [#787](https://github.com/dan-petty/devops-cli/issues/787)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/review

## Description
f93231b (#738) changed the base-revision read in `_fetch_git_file_content` (`commands/analyze.py`) to `git --no-pager show -- <rev>:<path>`. Git reads everything after `--` as a pathspec, so the command printed the head commit's header instead of the file and exited 0. The base file never parsed, so `symbols_removed` was always empty, every head symbol counted as added, and the "cites a removed symbol" check never fired. `test_apply_symbol_delta_to_meta` runs with `base=None` and no git repository, so no test caught it.

The read is `git --no-pager show <rev>:<path>` again. The revision and path are validated before the call (safe-ref and safe-relpath patterns, no leading `-`, no `..`), so dropping `--` needs no other guard.

Enhanced branch analyses written since f93231b cached every head symbol in `symbols_added` and none in `symbols_removed`, and `_try_reuse_branch_file_meta` keeps any non-empty cached delta for an unchanged file, so those analyses must be regenerated with `devops analyze branch --update-all`.

## Acceptance Criteria
- [x] The base revision's file is read again. `test_fetch_git_file_content_reads_the_base_revision` builds a real repository under `tmp_path` and reads `mod.py` at `main`: it returns `"def kept(): pass\ndef gone(): pass\n"`. Against f93231b it returned the `commit ...` header of the branch head.
- [x] A test against a real git repository removes a symbol and asserts it appears in `symbols_removed`. `test_apply_symbol_delta_reports_a_symbol_removed_since_the_base` removes `gone` and adds `added` on a `feature` branch, and `_apply_symbol_delta_to_meta` with `base="main"` gives `(["gone"], ["added"], ["kept"])` for removed, added and retained. Against f93231b it gave `([], ["added", "kept"], [])`.
- [x] `uv run devops ci` passes.
