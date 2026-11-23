# Proposal

## Why

The stage planner is a custom engine: its own read tools (`stage_tools.py`), a toolbox (`stage_toolbox.py`), gate returns, a gate extension and a schema retry (#6705). The owner decided that stage runs on the stock `Coder` agent of pydantic-ai-harness with upstream `RequireVerification` (#6528, comment 7053539044). On 2026-11-23 the owner decided that #6705 builds the `Coder` agent and the phases of the stage Job as one design (#6705, comment 7090472687). The phases are `prepare`, `agent` and `publish`. The `Coder` agent has a real shell, so it runs only in an `agent` phase that holds no GitHub credential. CronJob `roadmap-stage` runs the whole Job in one container with the App key until #6814 splits it. So `--phase all` keeps the current engine in one process until then.

## What Changes

- `devops roadmap stage --job-item <n> --confirm` takes `--phase prepare|agent|publish|all` and `--work <folder>`. `all` stays the default and runs `run_stage_job` in one process with no run file, as on `main`. A phase other than `all` needs `--job-item`, `--confirm` and `--work`. `--source` goes only with `prepare` and `all`.
- `prepare` holds the App key and runs no agent. It reads the round of the item and makes the writes that need no model. It decides the job-time premise, the false premise of the body probe and the blocker of an open plan.
- When no decision ends the run, `prepare` makes a full clone at the tip of the default branch. It commits the scaffold of the change folder with its own date, and writes `state/` and the inputs of the agent.
- `agent` holds the model key only. It refuses the App key, `GH_TOKEN`, `GITHUB_TOKEN` and a gh login. It runs stock `Coder` with its stock shell, and `RequireVerification` with three checks and `exempt_paths=()`.
- `LocalWorkspace` gives each command of the agent a scratch `HOME` and `DEVOPS_CLI_CONFIG`, so the checks of the agent read the settings of `publish`.
- The three checks are `devops openspec check`, `openspec validate <change> --strict` and `devops roadmap plan-recheck --source . --branch HEAD` with `--base`, `--candidate` and `--issues`.
- The agent phase writes the patch of the change folder, the body candidate and a `StageOutcome`. The outcome holds an end, the failed checks as an enum, and fixed count fields.
- `publish` holds the App key and reads `state/` and the outputs of the agent as data. Its own checks decide the ends `ended` and `unverified`. It accepts `timeout` only after the end time of `state/`.
- `publish` pushes once: the writer calls `publish_patch`, with the checks in `before_push`. They allow only the files of a plan, refuse a secret and another date, and run the three checks on the new tree.
- A fixed list of findings ends as `ci_infra`. The list holds the gate checks `version`, `configuration`, `skills` and `instructions`, a missing tool, and a network or GitHub error. A plan whose only finding is `group-over-budget` stops with `_stop_on_budget`. Each other finding ends as `plan_defect`.
- `publish` counts an end `ci_infra` of the agent toward `roadmap.stage.plan_defect_limit`. `provider` and `spend_limit` keep their waits and no count, as the owner rule on outages says.
- A new builder, `stage_candidate.py`, makes the title and the body with `staging_title`, `pull_request_body` and the closing-keyword stop. `plan-recheck` and `publish` both use it.
- `publish` cleans each text and fits each comment before it calls the writer of `--phase all`, and the writer works in a clone of `publish`. It then checks in.
- `devops roadmap plan-recheck --base <sha>` makes no fetch and reads no ref of the default branch. It judges each folder that `git diff --name-only <sha>..<branch>` names. The judge adds `staged_problems` and the test references of the removal scan, and exits 1 for a folder that is not `ok`.
- `--candidate <file>` gives the body candidate to the title and body rules. `--issues <file>` reads the issues from a listing file, and the command opens no store.
- The new prompt `roadmap_stage_coder.md` tells the agent how to write the plan and the candidate, commit them and run the three checks.
- This change deletes no code of the old engine, and the writer of `--phase all` keeps its behavior. #6846 deletes the old engine after #6814 is live, and takes the second acceptance criterion of #6705.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-stage/phases`: The stage Job takes a phase and a run folder, The default phase runs the stage Job in one process, Prepare decides what needs no model, Prepare writes the run of the agent, The agent phase holds no GitHub credential, The stage agent is stock Coder with the three checks, The agent phase hands over only what publish reads, Publish trusts no end that the agent reports, Publish counts only the ci_infra end of the agent toward the split limit, Publish allows only the files of a plan, Publish checks the plan files in its one push, Publish classes the findings of its checks, Publish builds the texts of the plan with the stage functions, Publish cleans each text before the writer of phase all, Publish writes from a clone of its own, The same plan gives the same publish in both forms, The separate phases share one time budget and one request budget

### Modified Capabilities

- `roadmap-plan-recheck`: A run with a base judges the folders that the branch changes, A run with a base adds the rules of the stage plan, The recheck reads the issues from a listing file

## Impact

- Code: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/stage/stage_job_phases.py` (new), `src/devops_cli/roadmap/stage/stage_agent.py` (new), `src/devops_cli/roadmap/stage/stage_candidate.py` (new), `src/devops_cli/ai/tasks/roadmap_stage_coder.md` (new), `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/phases/patch.py`, `src/devops_cli/core/process.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py` (new), `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `tests/roadmap/stage/test_roadmap_stage_agent.py` (new), `tests/roadmap/stage/test_roadmap_stage_agent_phase.py` (new), `tests/roadmap/stage/test_roadmap_stage_publish_checks.py` (new), `tests/roadmap/stage/test_roadmap_stage_publish.py` (new), `tests/support/fakes/roadmap_store.py`
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/plan-recheck.md`, `docs/adr/0036-the-stage-agent-runs-stock-coder-and-publish-checks.md` (new), `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`, `docs/commands/roadmap.md` and `docs/ENV_VARS.md` (generated)
- Production: none until #6814. CronJob `roadmap-stage` passes no `--phase`, so it keeps `run_stage_job` and the writer as they are.

## Feasibility

- The premise holds for the phases and fails for the deletion. `k8s/devops/cronjob-stage.yaml:86` has the one container `stage`, and lines 105 and 110 give it `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY`.
- The Service starts each Job with `roadmap stage --repo <repo> --job-item <n> --confirm` and no `--phase` (`src/devops_cli/roadmap/stage/stage_submit.py:325`). So `--phase all` must keep `run_stage_job` (`src/devops_cli/roadmap/stage/stage_job.py:446`) until #6814 is live. The deletion is re-scoped to #6846.
- The old engine has other users that #6846 handles: the fix-plan row (`src/devops_cli/roadmap/run.py:815`), `devops roadmap step fix-plan` (`src/devops_cli/commands/roadmap_step_fix_plan.py:98`) and the golden-set runs (`src/devops_cli/roadmap/stage/stage_eval_run.py:55`).
- `RequireVerification` of pydantic-ai-harness 0.71.0 (`pyproject.toml:41`) does not run the checks. It reads the shell commands of the agent. A run passes it when one check ran after the last edit and each recorded check passed (`require_verification/_capability.py:281`).
- `exempt_paths` defaults to `('*.md', '*.mdx', '*.rst')` (line 137), so the plan files count as edits only with `exempt_paths=()`. `CompletionUnverifiedEvent` comes only after an edit that the capability sees. A script run as `python3 <file>` matches no edit pattern (line 65).
- `Coder` 0.71.0 builds its shell with `default_timeout=MAX_FOREGROUND_WAIT`, 270 s (`coder/_capability.py:294-300`). So the agent uses the shell as it is. `LocalWorkspace` passes only `PATH`, `HOME`, `LANG`, `LC_ALL` and `LC_CTYPE` to a command, plus its `env` (`capabilities/local_workspace.py:61`).
- `devops roadmap plan-recheck --branch` exits 0 when the branch adds refusals. `tests/commands/test_roadmap_plan_recheck_cmd.py:165` asserts it, and the first commit of this plan got the result `new-plan` with exit 0. So the check needs a fail rule.
- `recheck_plans` fetches `origin/<default>` on each run (`src/devops_cli/roadmap/plan_recheck.py:449` calls `read_planned_changes`, which runs `git fetch` at `src/devops_cli/roadmap/planned.py:98`). The default branch moves, and the review of #6841 counted 26 of its 33 folders as not `ok`. So the fail rule compares with the base of `prepare`, and a run with `--base` makes no fetch.
- `default_branch` reads `refs/remotes/origin/HEAD` (`src/devops_cli/roadmap/clone_git.py:56`). The repository of `publish_patch` has no such ref, so with a base the caller gives the default branch.
- `plan-recheck` reads the open issues from the store (`src/devops_cli/commands/roadmap.py:1156`, `src/devops_cli/roadmap/plan_recheck.py:456`). The agent phase reads GitHub data only from the files of `prepare` (#6705, comment 7090472687), so `prepare` writes an issue listing.
- The whole listing of the repository is 11,291,737 bytes for 828 issues (review of #6841, 2026-11-23). The limit of a run file is 1 MiB (`src/devops_cli/config/constants.py:3885`). `IssueRecord` needs a title and a URL (`src/devops_cli/roadmap/stores/store.py:727-729`). So the listing holds those fields, and only the record of the item holds a body.
- Timing on the devcontainer, 2026-11-23: `plan-recheck --source . --branch HEAD` judged every folder twice in 166 s, and `devops openspec check` took 15 s. A run with `--base` judges only the folders that the branch changes. The task that builds it measures it on a clone of `main`.
- `devops openspec check` passed in 57 s with the proxies at a closed port and `GIT_ALLOW_PROTOCOL=file` (2026-11-23). It needs github.com only when the committed skills differ from a regeneration.
- `devops openspec check` refuses an `openspec` whose version is not the pin of `package-lock.json` (`src/devops_cli/openspec/gate.py:113`), and the stage Job runs no bootstrap (`k8s/devops/cronjob-stage.yaml:88`). The gate names its checks in `GateCheck` (`src/devops_cli/openspec/gate.py:76`). The overlap check names changes and no file (`src/devops_cli/openspec/gate.py:181`), so a fixed list of checks decides `ci_infra`.
- `_check_removal_references` raises for a test reference that the plan does not handle (`src/devops_cli/roadmap/stage/stage.py:1296`). None of the three checks runs that scan today, so `plan-recheck --base` runs it.
- `folder_problems` leaves out the title and body rules of `title_body_problems` (`src/devops_cli/roadmap/plan_check.py:244`). So `plan-recheck --base` runs `staged_problems` (line 547) with the title and the body of the candidate.
- On `main`, `OverBudget` stops before the file findings, and `_stop_on_budget` asks the owner and records no failure (`src/devops_cli/roadmap/stage/stage.py:4103`).
- The owner rule says that an outage of the provider, GitHub or the cluster does not count toward the split (`src/devops_cli/roadmap/stage/stage_job.py:35`, `src/devops_cli/config/settings.py:1440`, `src/devops_cli/roadmap/stage/stage_submit.py:28`).
- The writer runs git in its source checkout: `_check_removal_references` (`src/devops_cli/roadmap/stage/stage.py:4021`), `_open_pull` (line 3807), `_moved_for` (line 3910), `_delete_rejected_branch` (line 4158) and `_reject_plan` (line 4174). So `publish` gives the writer a clone of its own.
- `PhaseOutputError` and `PublishRefusedError` are `RoadmapImplementError` (`src/devops_cli/exceptions/roadmap.py:70` and line 76), which maps to `ci_infra` (`src/devops_cli/roadmap/failure.py:183`). `RoadmapStageError` maps to `plan_defect` (line 179).
- pydantic-ai stops a run after 50 requests by default (`pydantic_ai/usage.py:559`). The agent run passes `UsageLimits(request_limit=None)`, and the time budget of the Job bounds it.
- The plan reader gives no summary for the title (`src/devops_cli/roadmap/plan_read.py:665`), so the summary comes from the body candidate. The round leaves out an item whose title summary does not fit (`src/devops_cli/roadmap/stage/stage.py:769`), so the summary of the issue title always fits.
- `pull_request_body` calls `safe_text` itself (`src/devops_cli/roadmap/stage/stage_change.py:3699`), so the builder calls `safe_text` no second time.
- The closed PR #6822 has parts to reuse (comment 7090465365). These are `--phase`, `--work`, `StageWriter.resume`, `finds_github_login`, the store fake `fail_read` and the test probes. Its `prepare` also fails the item on a failed read.
- The first checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` fails on the base because `recheck_plans` takes no base. `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_agent.py` fails on the base because `stage_agent` does not exist.

## Existing Tool Considered

pydantic-ai-harness 0.71.0 covers the agent. `Coder` gives the file tools, the shell and the context controls, and `LocalWorkspace` gives the clone. `RequireVerification` sends an unverified run back to its checks, and `Hooks` gives the event of an unverified end. The implement step already uses `Coder` and `LocalWorkspace` (`src/devops_cli/roadmap/implement/implement_step.py:783`). The phases of ADR 0030 (`src/devops_cli/roadmap/phases/`) cover the run folder, the read of the outputs as data, the patch and the push with a lease. The change builds only the stage glue of the three phases, the prompt, the builder of the texts and three options of `plan-recheck`. That is about 1,500 lines of source and 1,500 lines of tests, about 3 million tokens and 2 working days. This pull request deletes no internal code. #6846 deletes `stage_tools.py` (511 lines), `stage_toolbox.py` (348 lines), the gate returns, the gate extension, the schema retry and their settings.

## Dependencies

None.
