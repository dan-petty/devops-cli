# Proposal

## Why

The stage job writes the OpenSpec change folder before implementation starts, so an implementation group must never write there. Issue #3285 reports a plan whose group `Write the change documents` listed a hallucinated path under `openspec/changes/`, and neither `StageGroup` nor `check_proposal` refused it, because `creates` made the path count as existing.

## What Changes

- `StageGroup` in `src/devops_cli/roadmap/stage_change.py` refuses a `changes` or `creates` path that is `openspec/changes` or sits under `openspec/changes/`, and allows the same paths in `reads`.
- `path_problems` in `src/devops_cli/roadmap/stage_paths.py` reports the same paths, so a recorded plan built without the schema is refused too.
- A new message `stage_bad_change_path` names the path and the rule.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` gains a path rule that forbids the change and the creation of a path under `openspec/changes/`.
- The roadmap stage tests cover the validator, the path check and the prompt rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A task group writes no file under openspec/changes, The path check reports a change-folder path, The stage prompt forbids a change-folder write

## Impact

- Code: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `probes` confirms each cited path: `The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.`, `The path `src/devops_cli/roadmap/stage_eval_gates.py` is a file of the staging commit.`, `The path `src/devops_cli/roadmap/stage_paths.py` is a file of the staging commit.` and `The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.`
- `probes` confirms that the test module the issue names does not exist yet, so the change creates no such file: `The path `tests/roadmap/test_stage_change.py` is no file of the staging commit. No commit in the history deleted or renamed it.`
- The code of `src/devops_cli/roadmap/stage_change.py` holds `class StageGroup(_Reply)` with `changes: list[RepositoryPath] = Field(min_length=1)` and `creates: list[RepositoryPath] = Field(default_factory=list)`, and its two model validators check only `creates` against `changes` and the rules of the kind. No validator names `openspec/changes`.
- The code of `src/devops_cli/roadmap/stage_paths.py` shows why the defect passed: `path_problems` skips a path that a group lists in `creates` (`created |= {path, *_folders_of(path)}`), so a created path under `openspec/changes/` is never reported.
- `check_proposal` in `src/devops_cli/roadmap/stage_change.py` calls `path_problems(proposal.groups, tree)`, so one check in `stage_paths.py` reaches the job and the replay of `src/devops_cli/roadmap/stage_eval_gates.py`.
- The first checks the implementation runs: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py`, and finally `uv run devops openspec check`.

## Existing Tool Considered

The existing validation layer covers the need: `_repository_path` and the `StageGroup` model validators in `src/devops_cli/roadmap/stage_change.py`, plus `path_problems` in `src/devops_cli/roadmap/stage_paths.py`. No external library applies, because the rule is a prefix test over paths that the reply already holds. Cost to build, keep and fix: about 5,000 tokens and 30 minutes. The change deletes no internal code; it adds one validator, one check and one message.
