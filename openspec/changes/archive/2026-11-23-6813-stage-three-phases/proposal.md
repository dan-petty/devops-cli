# Proposal: #6813

## Why

#6705 gives the stage agent a real shell, and the agent phase must hold no GitHub credential. Today `devops roadmap stage --job-item <n> --confirm` runs the stage Job in one process, with the App key and the model key, and the command has no `--phase` option. The implement and fix-checks jobs run on the three phases of ADR 0030 already (#3702, #6601). Closes #6813.

## What Changes

- `devops roadmap stage` takes `--phase prepare|agent|publish|all` and `--work <folder>`, as the implement and fix-checks jobs do. A phase other than `all` needs `--job-item` and `--confirm`. `all` stays the default, so CronJob `roadmap-stage` does not change.
- `prepare` reads the round of the item and makes the writes that need no model (`begin_stage`), reads the CI job-time premise, clones the staged commit into `work/` with no blobs (`clone_staged`), and writes the state file and the inputs of the agent. A round that leaves the item out, and a premise that decides the item, end the Job in `prepare`.
- `agent` plans the item in that clone with the current planner (`plan_targets`) and no store, and writes the result to `out/outcome.json`. It refuses to start with the App key or a GitHub token (`held_github_credentials`, which `require_agent_runner` uses too), or with a gh login that the token lookup finds (`finds_github_login`).
- The agent hands over only what the model made: the proposal, the shorter text of the body, the review findings, the counts and a compact trace. `publish` reads the state file and the outcome as data, builds the result from the state of `prepare` with the steps that the planner runs after the model answers (`build_plan`), and writes it with `StageWriter`: `push_plan`, then the draft pull request.
- `run_stage_job` runs the three phases in one process. `plan_stage` keeps its behavior: its parts are `begin_stage`, `store_reads` and `plan_targets`.

## Capabilities

- `roadmap-stage/job`: the phases of the stage Job, the refusal of a GitHub credential in its agent phase, and the read of its run files as data.

## Impact

The CronJob and the Service do not change: the Job runs `--phase all`, which runs the three phases in one process and holds both keys, as before. In an agent phase of its own, the GitHub reads of the planner (`read_issue`, `find_issues`, the files of a named pull request and the open pull requests that meet a cited path) answer that GitHub cannot be read. #6814 runs the phases in three containers, and #6705 replaces the planner.

## Feasibility

On `main`, `devops roadmap stage` has no `--phase` option, and `stage/stage_phases.py` holds only `push_plan` and `delete_plan_branch`. The planner (`_planner_of`) takes any clone at the staged commit, and it reads the store only through the reasons of the rejected plans, `comments_on`, `dependency_title` and `open_creates`, which `prepare` can read before the agent phase. Each GitHub read of the planner turns a failure into an answer of the tool or into no entry (#3240), so the planner runs with no GitHub credential. Each result type of the planner is a dataclass that pydantic `TypeAdapter` writes and reads as JSON. The new tests fail on `main` with `ImportError` (no `prepare_stage_job`) and exit code 2 (no `--phase`), and pass with this change.

## Existing Tool Considered

`roadmap/phases/` holds the run folder, the read of a run file as data and the patch and publish already (#6601, #6655), and pydantic `TypeAdapter` gives the JSON form of the results. The change reuses them and adds no tool.
