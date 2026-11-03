# Tasks

## 1. Read a change folder into a StageProposal

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/plan_read.py` (new), `tests/roadmap/test_roadmap_plan_read.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_plan_read.py` with a case that renders a proposal through `render_change`, reads the files back with `read_change`, and asserts that `groups`, `specs`, `criteria` and `skip_specs` equal the original, plus a case of a `tasks.md` with no `## Criteria` section, and verify that `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [ ] 1.2 Add `read_change(files: Mapping[str, str]) -> StageProposal` to `src/devops_cli/roadmap/plan_read.py`. It reads `.openspec.yaml` for `skip_specs`, `proposal.md` for `why`, `what_changes`, `feasibility` and `existing_tool`, `design.md` for `decisions` and `rejected`, each `specs/<capability>/spec.md` for `purpose` and for the `ADDED` and `MODIFIED` requirements with their scenarios, and `tasks.md` for the numbered groups, their files, their tasks of each kind and the `## Criteria` section. `summary` and `pull_request_body` come from the pull request, not from the folder, and verify that `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` passes

## 2. Run the stage gates and the pull request checks on a plan

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_validate.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/openspec/tool.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/plan_check.py` (new), `tests/roadmap/test_roadmap_plan_check.py` (new).

- [ ] 2.1 Write `tests/roadmap/test_roadmap_plan_check.py` with a fake pull request that holds a head tree, a title, a body and check runs, and a fake `OpenSpecTool`. Assert that a missing path gives the `MESSAGES.roadmap` missing-path message and exit 1; that a wrong title, a body with no `Plans #`, a body with `Closes #`, and a failed or missing `Semantic PR title` check each give their rule and exit 1; that a moved `MODIFIED` base requirement names the capability and the requirement; and that `check_proposal` and `validate_change` are called with no model client built, and verify that `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/roadmap/plan_check.py`. It finds the issue number in the `Plans #` line of the body, fetches `refs/pull/<number>/head` in the checkout, reads the change folder of that issue with `git show` and the head `StagedTree` with `git ls-tree`, turns a reader error into a problem that names the file, and builds the `StageProposal` with `read_change`. It calls `check_proposal` with the capability names and the requirement names of the base specs and the head `StagedTree`, and `validate_change` with the change files. It adds the title rule (`staging_title` of the issue number and the summary after `plan #<number> `, and the text after the colon within `SUMMARY_MAX_CHARS`), the body rules against `BODY_MAX_CHARS` and `closing_keyword_in`, the `Semantic PR title` conclusion, and the moved base spec of each `MODIFIED` requirement between the parent of the commit that added the folder and the pull request base. Each problem is a record of `path`, `rule` and `message`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` passes

## 3. Wire the plan-check command and its options

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_plan_check_cmd.py` (new).

- [ ] 3.1 Write `tests/commands/test_roadmap_plan_check_cmd.py` with a case that runs `plan-check` with `--json` over a fake pull request and asserts that stdout parses as a JSON array of objects with `path`, `rule` and `message` and that the exit code is 1, and a case that runs it with `--dry-run` and asserts that the printed requests name each read and that no GitHub request is sent, and verify that `uv run devops ci test tests/commands/test_roadmap_plan_check_cmd.py` fails on the base
- [ ] 3.2 Add `plan_check_cmd` to `src/devops_cli/commands/roadmap.py` with the argument `<pull-request>`, the options `--repo`, `--json` and `--dry-run`, and the dry-run class that `src/devops_cli/commands/roadmap.py` already imports. It prints one line for each problem with its file, its rule and its message, or the JSON array with `--json`, and exits 1 when it finds one. With `--dry-run` it prints the requests through `render_dry_run` and makes none. Add the help text of the command and the texts of its problems to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/commands/test_roadmap_plan_check_cmd.py` passes

## 4. Document plan-check

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`. Changes: `docs/roadmap/plan-check.md` (new), `docs/ROADMAP_WORKFLOW.md`.

- [ ] 4.1 Write `docs/roadmap/plan-check.md` with what the command reads, the checks it runs, its options and its exit code, and link it from the notes of the plan step in `docs/ROADMAP_WORKFLOW.md`. Regenerate the command reference with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes
- [ ] 4.2 `docs/roadmap/plan-check.md` tells a person and an agent what the command checks and how to read its output. `docs/ROADMAP_WORKFLOW.md` links it from the plan step, and the generated command reference holds its entry, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
