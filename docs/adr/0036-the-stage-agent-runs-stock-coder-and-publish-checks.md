---
status: proposed
date: 2026-11-23
decision-makers: [owner]
issue: 6705
amends: ["0030"]
---

# The stage agent runs stock Coder, and publish checks

## Context and Problem Statement

The stage planner is a custom engine: its own read tools, a toolbox, gate returns, a gate extension and a schema retry. The owner decided that stage runs on the stock `Coder` agent of pydantic-ai-harness with the upstream `RequireVerification` (#6528, #6705). `Coder` has a real shell, and CronJob `roadmap-stage` runs the stage Job in one container with the App key until #6814 gives it three containers.

## Decision Drivers

- The shell of an agent must not run next to a GitHub credential ([ADR 0030](0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md)).
- A check that the model can skip, or report wrongly, is no gate.
- Production keeps its behavior until the stage Job gets its containers.

## Considered Options

- **Stock `Coder` in an agent phase of its own, and `publish` as the check**: chosen.
- **Stock `Coder` in `--phase all`**: rejected, because the shell would run in the container that holds the App key.
- **Trust the end and the checks that the agent reports**: rejected, because an agent can break its clone and report an end that retries, or skip a check.
- **Keep the custom engine of stage**: rejected, because the owner chose the stock agent, and the engine copies the coding capability of the harness.

## Decision Outcome

Chosen option: "Stock `Coder` in an agent phase of its own, and `publish` as the check", because it keeps the shell apart from the App key and judges the plan outside the model.

- `devops roadmap stage --job-item <n>` takes `--phase prepare|agent|publish|all` on the run folder of ADR 0030. `all` stays the default and runs the stage Job in one process until #6814.
- The `agent` phase holds the model key only. It refuses the App key, each GitHub token and a gh login. It runs stock `Coder` in the clone of `prepare`, with `LocalWorkspace`, no repository context, no `delegate_task`, and `RequireVerification` with three checks: `devops openspec check`, `openspec validate --strict` and `devops roadmap plan-recheck` with the base of `prepare`. The agent writes the plan files and a body candidate. The phase hands over a patch, the candidate and an outcome with no text of the model.
- `publish` is the check. It reads the outputs of the agent as data, trusts no end that the agent reports, and allows only the files of a plan. It runs the three checks again on the tree that it pushes, in `before_push` of its one `publish_patch`. It builds the title, the body and the labels itself, with the functions of the stage job. A plan that a check refuses pushes no branch.

### Consequences

- Good, because the stage agent uses the stock tools of the harness and no custom tool.
- Good, because the model sees each rule that `publish` runs, in the same run.
- Bad, because the old engine stays for `--phase all`, fix-plan and the golden-set runs until #6846 deletes it.

### Confirmation

- `tests/roadmap/stage/test_roadmap_stage_agent.py`: `Coder` with the stock capabilities, `RequireVerification` with the three checks, and no custom tool.
- `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`: the agent phase refuses each GitHub credential.
- `tests/roadmap/stage/test_roadmap_stage_publish_checks.py` and `tests/roadmap/stage/test_roadmap_stage_publish.py`: one test for each check of `publish`, and the same push and writes as `--phase all` for one plan.

## More Information

- This record amends ADR 0030: the stage Job is a roadmap step on its phases.
- The change: `openspec/changes/archive/2026-11-23-6705-stage-agent-stock-coder/`. The issues: #6705, #6528, #6814 and #6846.
- [The phases of the stage Job](../roadmap/stage.md#the-phases-of-the-stage-job).
