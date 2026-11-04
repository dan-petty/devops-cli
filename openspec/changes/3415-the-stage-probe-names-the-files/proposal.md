# Proposal

## Why

The probe of #3011 reports a cited bare file name as missing when the name exists only under a folder, so a plan can dismiss a file that exists; #3415 makes the probe name the same-name files as candidates.

## What Changes

- The probe lists the files of a cited bare name that the staged tree holds under a folder, and names them as candidates, when the root holds no such file.
- The probe says a cited path with a same-name file is no file at the *root* of the staging commit, not that it is no file of the commit.
- The probe test asserts that a cited bare name with no root file gets the file under `src/devops_cli/roadmap/` as its candidate.
- The probe reads the tree of the staging commit once, on the first cited path that is missing, within its command bound, and keeps a cited path that exists at the root on its present line.
- The test that pins the command kinds of the probe adds `ls-tree`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The probe names the files of a cited bare name

## Impact

- Code: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_probe.py`

## Feasibility

- `probes` shows the false report of the issue: "The path `stage_specs.py` is no file of the staging commit. No commit in the history deleted or renamed it."
- `probes` shows the file that the name resolves to: "The path `src/devops_cli/roadmap/stage_specs.py` is a file of the staging commit."
- `read_file` of `src/devops_cli/roadmap/stage_probe.py` shows the literal check in `_Run.path`: `code, _ = self.git("cat-file", "-e", f"{self.sha}:{name}")`, with no same-name lookup.
- `read_file` of `src/devops_cli/roadmap/stage_paths.py` shows the rule to reuse: `StagedTree.same_name` returns the files of the name of `path`, sorted, at most `SAME_NAME_MAX`, and `path_problems` names them in its hint.
- `read_file` of `tests/roadmap/test_roadmap_stage_probe.py` shows the probe tests that the new case joins.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py`, the probe test suite on the changed module.
- Second check against the real system: `uv run devops ci lint` and `uv run devops ci typecheck`, the static gate of the repository on the changed module.

## Existing Tool Considered

No open, maintained tool or library covers this need: it is a lookup inside the repository's own `stage_probe` module, which already reads the staged tree through `StagedTree.same_name` in `src/devops_cli/roadmap/stage_paths.py`.

## Dependencies

None.
