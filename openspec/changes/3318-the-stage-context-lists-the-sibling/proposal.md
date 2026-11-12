# Proposal

## Why

The stage context shows the files that an issue cites, and no other place where the same kind of file lives. A plan that adds `.claude/skills/new-scaffold/SKILL.md` therefore reaches one agent root. The repository commits the OpenSpec skills in `.claude/skills/`, `.agents/skills/` and `.kilocode/skills/`, and an agent reads only its own root. #3318 makes the stage context list the other trees that hold a file of the same shape, and the prompt asks the plan to cover each tree or to give a reason for one tree.

A sibling tree is a top-level tree such as `.agents/skills/`. The list holds a tree only when the tree holds a file whose relative path matches the glob of the created file. A fixed list of known trees would miss a new file family, so the job derives the glob from the path and matches the files of the staged commit.

## What Changes

- Add `sibling_trees(path, files)` to `src/devops_cli/roadmap/stage_paths.py`. It replaces the first path segment and the directory before the file name with `*`, matches the tracked files with `PurePosixPath.full_match`, and returns the sorted first two segments of each matching file, without the tree of `path`.
- Add the `Sibling trees` section to the request context of `src/devops_cli/roadmap/stage.py`. The section lists the trees of each cited path that the staged tree does not hold, and it is present only when the list has at least one tree.
- Add the message strings for the section to `src/devops_cli/lang/en/messages.py`.
- Add the rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md` that the plan writes the file in each listed tree, or states in `decisions` why one tree is enough.
- State the section and the rule in `docs/roadmap/stage.md`.
- Add the requirements to `roadmap-stage/context`, with the tests of the helper and the request.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/context`: The stage context lists the sibling trees of a created file, The stage context omits a single sibling tree, The stage prompt asks for each tree or a reason, A sibling tree matches the relative path, The sibling trees are sorted

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `openspec/changes/3318-the-stage-context-lists-the-sibling/proposal.md`, `openspec/changes/3318-the-stage-context-lists-the-sibling/design.md`, `openspec/changes/3318-the-stage-context-lists-the-sibling/tasks.md`, `openspec/changes/3318-the-stage-context-lists-the-sibling/specs/roadmap-stage/spec.md`
- Tests: `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probe gives `The path `src/devops_cli/roadmap/stage_paths.py` is a file of the staging commit.`, so the helper has a home in the path module.
- `src/devops_cli/roadmap/stage_paths.py` holds `class StagedTree` with `self._files = frozenset(files)` and `def has(`, so the helper can read the files of the staged commit without a new git command.
- `src/devops_cli/roadmap/stage.py` holds `def _request(` and calls `collect_context(self._source, self._sha, item.body, max_tokens=...)`, so the request builder is the one place that adds the section.
- `src/devops_cli/roadmap/stage_probe.py` holds `probe_premise(source: Path, sha: str, body: str)`, which reads `cited_paths(body)`; the staged tree shows which cited paths exist, so a cited path that the tree lacks is a path that the plan creates.
- `git ls-files` shows `.claude/skills/openspec-apply-change/SKILL.md`, `.agents/skills/openspec-apply-change/SKILL.md` and `.kilocode/skills/openspec-apply-change/SKILL.md`, so the skill family has three sibling trees and the premise holds.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, then `uv run devops openspec check`.

## Existing Tool Considered

Python's `pathlib` standard library holds `PurePath.full_match`, so the change adds no dependency and no new tool. No open, maintained tool covers the stage context of this repository. The change builds one helper: 6,000 tokens to build, 1,000 tokens per month to keep and fix, and half a day of elapsed time. It deletes no internal code.
