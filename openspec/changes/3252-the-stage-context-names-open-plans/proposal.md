# Proposal

## Why

A plan is written without knowledge of the open plans and pull requests that edit the same files (#3252). Two plans that edit `INSTRUMENTS` or the generated `docs/TELEMETRY.md` can merge one after the other and force a regenerate, and nothing checks the other senders of a shared counter.

## What Changes

- Add `src/devops_cli/roadmap/stage_overlap.py`: it reads the open pull requests with their changed files, compares them with the paths cited in the issue body, and lists each overlap with its number, title, state, plan mark and shared paths.
- Read the open pull requests in one GraphQL request for each 100 through the GitHub session, so each request counts once in `devops_cli_github_requests_total`.
- List the other files that hold a cited metric name, from `git grep -w` at the staged commit, in the stage context.
- Add the `overlaps` and `metric_senders` keys to the stage request in `src/devops_cli/roadmap/stage.py`.
- Add the `dependencies` field to `StageProposal` in `src/devops_cli/roadmap/stage_change.py`, render it as `## Dependencies`, and refuse an empty one when the context lists an overlap.
- Add the `dependencies` key and rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and report model replay scores before and after per `docs/ROADMAP_WORKFLOW.md`.
- Tests give the builder a fake client and a fake tree, so no test reaches GitHub.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage context lists an overlapping pull request, A plan pull request carries a plan mark, A cited metric lists its other senders, The gate refuses an empty Dependencies part on an overlap, The stage prompt states the Dependencies rule, The overlap read costs a stated number of GitHub requests

## Impact

- Code: `src/devops_cli/roadmap/stage_overlap.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_overlap.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `read_file` on `src/devops_cli/roadmap/stage.py` showed `check_proposal(proposal, self._known, self._tree_of(target, proposal), requirements=self._requirements, issue_body=target.item.body)` inside `_Planner._settle`, so the gate reads the reply and the staged tree and is the place for the overlap rule.
- `read_file` on `src/devops_cli/roadmap/stage.py` showed `_Planner._request` builds the request with the keys `number`, `title`, `body`, `context`, `capabilities`, `budget` and `probes`, so the overlap list joins it there.
- The probe answered "The path `docs/TELEMETRY.md` is a file of the staging commit", and `read_file` on it showed the row `devops_cli_github_requests_total` and the text "Each metric is an entry of `INSTRUMENTS` in `src/devops_cli/telemetry/instruments.py`", so a cited metric name appears in more than one file.
- The probe answered "The path `src/devops_cli/telemetry/instruments.py` is a file of the staging commit", and `read_file` showed `INSTRUMENTS` holding the declared instruments, so the list of metric names is in place.
- The probe answered "The path `src/devops_cli/roadmap/stage_eval_gates.py` is a file of the staging commit" and "The path `openspec/changes/archive/2026-11-01-3010-stage-refuses-missing-paths/design.md` is a file of the staging commit", so the path extraction of the earlier path rule is in place.
- `read_file` on `docs/adr/0001-github-is-the-roadmap-source.md` showed it links `0016-labels-hold-the-roadmap-items-fields.md`, which holds item fields and no request budget. The request budget is `devops_cli_github_requests_total` in `docs/TELEMETRY.md`.
- `list_files` on `src/devops_cli/ai/tasks/` showed `roadmap_stage_change.md`, so the stage prompt that the change edits is that file.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_overlap.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py`, then `uv run devops openspec check`.
- A test cannot reach GitHub, so the overlap tests give the builder a fake client and a fake tree. The first real read is checked by `uv run devops roadmap stage --dry-run`, which lists the requests and sends none.

## Existing Tool Considered

`gh` is open and maintained and the repository already runs it, but it compares no path sets, renders no context entry and refuses no plan. `gh pr list --json number,title,state,files` gives the pull requests and their files, and `git grep -w` gives the files that hold a name. The change writes that glue: about 200 lines with tests, about 100k tokens to build, keep and fix, and about one day of elapsed time. It deletes no internal code.
