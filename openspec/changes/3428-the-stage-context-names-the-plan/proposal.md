# Proposal

## Why

The stage job plans a change and writes the files of its OpenSpec change. The plan for #3393 told the implement job to add a reader that builds a `StageProposal` from the change folder. That reader already exists: `read_change` in `src/devops_cli/roadmap/plan_read.py` reverses `render_change`, and `plan_check` calls it to read a plan pull request. The stage context names neither `read_change`, nor the revision reads, nor the gate `stage_change.check_proposal`, so the planner proposed a second reader and spent tokens on a part that exists. #3428 makes the stage context name the reader, the revision reads and the gate, so a plan cites them.

## What Changes

- The stage request context gains a `### Plan reader and gate` section that names `plan_read.read_change`, `plan_read.tree_files`, `plan_read.files_at`, `plan_read.change_root` and `stage_change.check_proposal`, each with its path and one line of purpose.
- The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` gains a rule that names `plan_read.read_change` when the plan builds a reader for a change folder, so the plan cites the reader that exists instead of planning a second one.
- `tests/roadmap/stage/test_roadmap_stage_plan.py` asserts that the request context of an item holds the plan reader entry and its path.
- `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` asserts that the prompt holds the reader rule.
- The change carries a spec delta because the request of the stage job and its prompt are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage context names the plan reader, The stage context names the revision reads, The stage context names the plan gate, The stage prompt names the existing plan reader

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds: the stage request context is built in `_Planner._request`, and the stage job appends one section to it. `src/devops_cli/roadmap/stage/stage.py:1010:context = collect_context(` builds the context, and `src/devops_cli/roadmap/stage/stage.py:1022:### Registry places` is the one section that the job appends.
- The plan corrects the claim that `check_proposal` calls `read_change`. The gate takes a `StageProposal`: `src/devops_cli/roadmap/stage/stage_change.py:1203:def check_proposal(` and `src/devops_cli/roadmap/stage/stage_change.py:1204:proposal: StageProposal,`. The reader has other callers: `src/devops_cli/roadmap/plan_check.py:507:proposal = read_change(change_files)` and `src/devops_cli/roadmap/implement/implement.py:398:proposal = read_change(files_at(self._source, rev, changed, operation=GIT_OPERATION))`.
- The probes confirm the reader: "The path `src/devops_cli/roadmap/plan_read.py` is a file of the staging commit." `src/devops_cli/roadmap/plan_read.py:472:def read_change(files: Mapping[str, str]) -> StageProposal:` shows the reader that reverses `render_change`.
- The probes also say: "The path `plan_read.file_texts_at` is no file of the staging commit. No commit in the history deleted or renamed it." No commit holds `file_texts_at`, and the archived plan of #3430 records it: `openspec/changes/archive/2026-11-05-3430-read-the-default-tree-once-per-run/proposal.md:38:It finds no `file_texts_at` and no `base_specs_at`. The change uses the real names.` The plan names the real readers `files_at`, `tree_files` and `change_root` and creates no reader.
- The revision reads exist in `plan_read`: `src/devops_cli/roadmap/plan_read.py:def files_at` returns the text of named paths at a commit, `src/devops_cli/roadmap/plan_read.py:def tree_files` lists the paths of a commit, and `src/devops_cli/roadmap/plan_read.py:def change_root` finds the change folder of an issue. The dependency of the issue is delivered: #3393 is archived under `openspec/changes/archive/2026-11-05-3393-the-implement-job-refuses-a-plan/`.
- The gate exists at `src/devops_cli/roadmap/stage/stage_change.py:1203:def check_proposal(`. The probes left it unprobed: "Not probed, the bound of 10 commands is reached: `stage_change.check_proposal`, ...".
- The paths of the issue moved. The modules are `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py` and `tests/roadmap/stage/test_roadmap_stage_plan.py`. The archived plan of #3287 records the move: `openspec/changes/archive/2026-11-07-3287-detect-obsolete-spec-requirements-on-command/proposal.md:37:The rename is no false premise: commit bff2f14f moved the modules into `src/devops_cli/roadmap/stage/`,`.
- The plan adds five entries to the context section, and the group 1 test asserts each of the five: `plan_read.read_change`, `plan_read.tree_files`, `plan_read.files_at`, `plan_read.change_root` and `stage_change.check_proposal`.
- `collect_context` needs a checkout of the repository at the staged commit: it reads the cited files with git.
- `files_at` needs a checkout of the repository: it reads each path of a commit with `git show`.
- `open_pulls` needs a network: `_read_overlaps` calls it to read the open pull requests of the repository.
- The plan changes the prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and `STAGE_EVAL_TRIGGER_PATHS` holds it: `src/devops_cli/roadmap/stage/stage_change.py:208:STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (` with `src/devops_cli/roadmap/stage/stage_change.py:209:"src/devops_cli/ai/tasks/roadmap_stage_change.md",`. The replay command is the value of `STAGE_EVAL_REPLAY`: `src/devops_cli/roadmap/stage/stage_change.py:217:STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"`, and the task states the words of `_STAGE_EVAL_SCORE_WORDS`: `src/devops_cli/roadmap/stage/stage_change.py:219:_STAGE_EVAL_SCORE_WORDS: Final[tuple[str, ...]] = ("score", "before", "after")`.
- The prompt that the job loads is the value of `_CHANGE_TASK`: `src/devops_cli/roadmap/stage/stage.py:679:_CHANGE_TASK: Final[str] = "roadmap_stage_change.md"`.
- The test of group 1 follows the existing request test: `tests/roadmap/stage/test_roadmap_stage_plan.py:549:assert "### Registry places" in request["context"]` reads the context of the request built by the fake model client.
- The first checks the implementation runs against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and `uv run devops roadmap eval stage --replay`.

## Existing Tool Considered

The internal reader `read_change` in `src/devops_cli/roadmap/plan_read.py` and the gate `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py` cover the need, and no open, maintained external tool or library covers an internal stage context. The change adopts them, adds one constant and one context section, builds no new tool and deletes no internal code. Written cost: about 4,000 tokens to build and test, about 1,000 tokens to keep and fix, and about 2 hours of elapsed time.

## Dependencies

None.
