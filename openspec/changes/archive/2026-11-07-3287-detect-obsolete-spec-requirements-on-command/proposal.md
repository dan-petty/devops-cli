# Proposal

## Why

Issue #3287 reports that the stage planner adds a requirement that a removed CLI command MUST NOT exist and leaves the base requirements that name the old command unchanged, so the archive writes a contradictory living spec. No check stops the next rename.

## What Changes

- Read the statement of each requirement of a base spec in `src/devops_cli/roadmap/stage/stage_specs.py`, so the stage job can give the plan check the text of each base requirement.
- Refuse a plan in `src/devops_cli/roadmap/stage/stage_change.py` when an added requirement removes a command or an option and a base requirement that names it is unmodified, or when a modified text keeps the name.
- Pass the base requirement texts from `src/devops_cli/roadmap/stage/stage.py` to `check_proposal`, and skip the check when a caller passes none.
- State in `src/devops_cli/ai/tasks/roadmap_stage_change.md` that a removed or renamed command or option needs a `modified` requirement for each base requirement that names it.
- List a file of the living spec before a source file in the answer of the tool `references` in `src/devops_cli/roadmap/stage/stage_references.py`.
- Add requirements to the capability `roadmap-stage` for the new check, the base texts it reads and the prompt rule, and change the requirement that orders the groups of a `references` answer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A base requirement that names a removed command is updated, The stale-command check reads the base requirement texts of its caller, The stage prompt requires a modified requirement for a removed command, The tool references keeps files of every group

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_references.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`

## Feasibility

- The probes confirm the premise at the staged commit: `The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.`
- The issue cites `src/devops_cli/roadmap/stage_change.py` and `src/devops_cli/roadmap/stage_references.py`, and the probes answer `The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`.` and the same for the references module, so the commit holds both files under `stage/` and the plan uses those paths.
- The rename is no false premise: commit bff2f14f moved the modules into `src/devops_cli/roadmap/stage/`, and `src/devops_cli/roadmap/stage/stage_change.py:def check_proposal` still holds the gate that the issue names.
- `src/devops_cli/roadmap/stage/stage_change.py:def _delta_problems` reads the base requirement names through `src/devops_cli/roadmap/stage/stage_change.py:571:problems.extend(_duplicate_problems(spec, requirements))` and judges no requirement text, so the new rule has a place beside it.
- `src/devops_cli/roadmap/stage/stage_specs.py:def read_spec` keeps only the names: `src/devops_cli/roadmap/stage/stage_specs.py:40:return BaseSpec(purpose, tuple(_REQUIREMENT.findall(text)))`, so the caller has no base text to give the check today.
- The stage job builds the names it passes with `src/devops_cli/roadmap/stage/stage.py:876:self._requirements = {name: spec.requirements for name, spec in specs.items()}`, and the planner reads the specs from the checkout at `read_base_specs`.
- The stage prompt holds no rule for a removed or renamed command: `src/devops_cli/ai/tasks/roadmap_stage_change.md:16:Never add a requirement with the name of one in its` and the bullet speaks of requirement names only.
- `src/devops_cli/roadmap/stage/stage_references.py:28:("source", "tests", "specs", "docs", "changes", "other")` puts a spec file after the source and the test files today.
- Precondition: `read_base_specs` in `src/devops_cli/roadmap/stage/stage_specs.py` reads the base specs from a checkout of the repository.
- Precondition: `StageTools.references` in `src/devops_cli/roadmap/stage/stage_tools.py` runs `git grep` in a checkout of the repository.
- Precondition: `_read_staged_file` in `src/devops_cli/roadmap/stage/stage.py` reads a cited file from a checkout of the repository.
- `check_proposal` and `read_spec` need no checkout, no client and no network: they read the reply and the spec text that the caller passes.
- The first checks of the implementation run the tests of each group: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py`.
- The plan changes `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/ai/tasks/roadmap_stage_change.md`, which are trigger paths of the stage eval, so one task states `uv run devops roadmap eval stage --replay` with the score before and after the change, as `docs/ROADMAP_WORKFLOW.md:313` asks.

## Existing Tool Considered

No open, maintained tool or library checks this repository's own spec delta against its living specs. The change extends `_delta_problems` and `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py`, and it deletes no code. Build cost: about 8k tokens to build, keep and fix, and 2 hours of elapsed time.

## Dependencies

- Pull request #3957 changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, the prompt that group 4 edits, so the two branches touch one file.
- Pull request #3944 changes `docs/ROADMAP_WORKFLOW.md`, which states the rule for a new gate of the stage job and the replay score.
- Pull request #3955 changes `docs/ROADMAP_WORKFLOW.md`, which states the rule for a new gate of the stage job and the replay score.
