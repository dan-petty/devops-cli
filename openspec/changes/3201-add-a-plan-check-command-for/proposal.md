# Proposal

## Why

The review of a plan pull request is manual, and the checklist drifts between prompts: one version flagged a `tuicr` line in `tasks.md` that `openspec/config.yaml` allows. Most of the checks are mechanical and the stage job already runs them on its own reply, but no command runs them on a plan pull request that already exists (#3201). This change gives the mechanical part one source that a person or an agent can run.

## What Changes

- Add `devops roadmap plan-check <pull-request>`, which reads the change folder at the head commit of a plan pull request and runs the stage gates on it with no model.
- Add a plan reader that builds a `StageProposal` from the files of a change folder, with a round-trip test against `render_change`.
- Report each problem with its file, its rule and the message of the stage job, and exit 1 when the command finds one.
- Add the checks of the pull request: the title form, the body length and its `Plans #` reference, and the conclusion of the `Semantic PR title` check.
- Report a `MODIFIED` requirement whose base spec text changed since the plan commit.
- Add `--json` for an agent and `--dry-run`, which prints the GitHub requests and sends none.
- Carry a spec delta: the command, its options and its messages are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-plan-check`: Plan-check reads the change folder at the pull request head, The plan reader builds a StageProposal from a change folder, Plan-check runs the stage gates with no model, Plan-check reports each stage problem, Plan-check checks the title of the pull request, Plan-check checks the body of the pull request, Plan-check reads the Semantic PR title check, Plan-check reports a base spec that moved since the plan, Plan-check prints JSON, Plan-check dry run makes no request

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/plan-check.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/commands/test_roadmap_plan_check_cmd.py`

## Feasibility

- `probes` reports `The path src/devops_cli/commands/roadmap.py is a file of the staging commit.`, and the same for `src/devops_cli/roadmap/stage_validate.py` and `src/devops_cli/roadmap/stage_change.py`, so the three files that the issue names exist.
- `probes` reports `The path openspec/config.yaml is a file of the staging commit.`, so the rules that the gates enforce are readable at the commit.
- `read_file src/devops_cli/roadmap/stage_validate.py` shows `def validate_change(` with `tool: OpenSpecTool, source: Path, change: str, files: Mapping[str, str]` and `) -> str | None:`, so the gate takes the change files and a checkout of the base specs and calls no model.
- `read_file src/devops_cli/roadmap/stage_change.py` shows `def check_proposal(` with `tree: StagedTree,`, `issue_body: str = "",` and `def render_change(` with `) -> dict[str, str]:`, so the gates take a `StageProposal` and the writer gives the files that the reader must read back.
- `read_file src/devops_cli/roadmap/stage_change.py` shows `from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS` and `BODY_MAX_CHARS: Final[int] = 800`, so the title and body limits already exist and the command reuses them.
- The first checks against the real system: `uv run devops roadmap plan-check <pull-request> --dry-run` lists the requests and sends none; `uv run devops roadmap plan-check <pull-request>` on a merged plan pull request prints no problem and exits 0; `uv run devops openspec check` validates the change folder itself.

## Existing Tool Considered

`openspec validate --strict` already checks the shape of a change and the project runs it in `src/devops_cli/roadmap/stage_validate.py`. It checks no path against the commit, no mirror folder, no pull request title or body, no `Semantic PR title` check and no moved base spec, so the change reuses it through `validate_change` and adds one reader and one command around it. Building a second validator would cost about 120k tokens and 6 hours, plus the cost of keeping two sets of rules in step with `openspec/config.yaml`. The change deletes no internal code: it shares `check_proposal`, `validate_change` and `render_change` with the stage job.
