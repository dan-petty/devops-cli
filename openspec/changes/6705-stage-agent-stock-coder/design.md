# Design

## Decisions

- **`--phase all` keeps `run_stage_job` in one process until #6814 is live.**: CronJob `roadmap-stage` runs one container with the App key and the model key (`k8s/devops/cronjob-stage.yaml:86`, lines 105 and 110), and the Service passes no `--phase` (`src/devops_cli/roadmap/stage/stage_submit.py:325`). A real shell must not run next to that key, and the owner asked for one process with no result file in between.
- **The `Coder` agent runs only in a separate `agent` phase.**: That phase refuses the App key, each GitHub token variable and a gh login, so the shell of the agent reaches no GitHub credential.
- **`publish` is the check.**: The agent writes the plan files and a body candidate, and `publish` reads them as data. It runs the three checks of the agent again on the new tree, before any push, with the same functions as the commands.
- **`publish` refuses only what the agent can see, plus the rules of the build and of security.**: A refusal that the checks of the agent cannot show ends in `plan_defect` on each run, and no run can fix it. So `publish` runs the three checks, the path rule, the secret scan, the date rule and the closing-keyword stop, and leaves `staged_problems` to the CI job `Plan Check`.
- **Every refusal of `publish` is `plan_defect`.**: `publish` raises `RoadmapStageError` for a refused output, a refused path and a failed check, so the item gets no `ci_infra` retry (`src/devops_cli/roadmap/failure.py:179`).
- **`prepare` writes the scaffold of the change folder.**: The scaffold holds the date of `prepare` in `.openspec.yaml`, and `devops openspec check` refuses each scaffold marker that the agent does not replace. So the date comes from `prepare`, and an empty plan fails the check.
- **The shell of the agent is the blocking `run_command` tool, with the time left of the budget as its limit.**: `plan-recheck --branch HEAD` took 166 s on the devcontainer, and the persistent `shell` tool returns a running command after at most 270 s with no result for `RequireVerification`.
- **The agent run has no request limit.**: The time budget of the Job bounds the run, as the owner rule asks: no hard cap that makes a Job fail.
- **`plan-recheck` gets a fail rule for the folders of a branch and a listing file.**: The command is the third check of the owner, and today it exits 0 on a refused branch and reads GitHub for its issues.
- **`publish` writes the plan with the writer of `--phase all`.**: `_stage_one` takes the push as an argument: `push_plan` for `--phase all`, and the push of the patch of the agent for `publish`. The pending mark, the draft, the record, the labels and the comments have one copy.
- **The outcome holds no text.**: `outcome.json` holds the end, one failure class of the agent set, the names of the failed checks as an enum, and counts. The only texts of the agent are the plan files and the body candidate.
- **The stage writer removes the control characters and fits each comment.**: `safe_text` runs once on each text, and the writer is the one place where each text reaches GitHub. A change of `safe_text` in `stage_change.py` would be a change of a check of the stage job, which `plan-recheck` sends to the golden-set replay.

## Rejected alternatives

- **Run the three phases of the `Coder` agent in `--phase all`**: `k8s/devops/cronjob-stage.yaml:105` gives the one container the App key, so the shell of the agent would run next to it in production until #6814.
- **Delete the old engine in this pull request**: `--phase all` needs `run_stage_job` until #6814 is live, and `src/devops_cli/roadmap/run.py:815`, `src/devops_cli/commands/roadmap_step_fix_plan.py:98` and `src/devops_cli/roadmap/stage/stage_eval_run.py:55` use the toolbox outside the stage Job.
- **Trust the verified end of `RequireVerification`**: a run is verified when one check ran after the last edit and each recorded check passed (`require_verification/_capability.py:281`), so a run with one of the three checks is verified.
- **Keep `exempt_paths` at its default**: the default is `('*.md', '*.mdx', '*.rst')` (`require_verification/_capability.py:137`), so an edit of a plan file would need no check.
- **The persistent `shell` tool of `Coder`**: `shell/_persistent.py:26` caps a foreground wait at 270.0 s, and a check that runs longer records no result.
- **Read the issues of `plan-recheck` from GitHub with no token**: the run with `env -i` and no token of 2026-11-23 read the public repository, but a private repository gives no such read, and the owner rule says that the agent reads GitHub data only from the files of `prepare`.
- **A new flag of `plan-recheck` for the fail rule**: an agent that leaves out the flag passes the check. The fail rule applies to the folders that a branch adds or changes, and a branch of a new gate changes no folder, so the gate review of `docs/roadmap/plan-check.md:130` keeps exit 0.
- **`PhaseOutputError` for a refused plan**: it is a `RoadmapImplementError` (`src/devops_cli/exceptions/roadmap.py:70`), which maps to `ci_infra` (`src/devops_cli/roadmap/failure.py:183`), so a refused plan would run again and again.
- **A trace of the agent in `outcome.json`**: the trace of PR #6822 kept tool answers, and its test `test_a_plan_with_200_full_searches_publishes` had to hold the outcome under the 1 MiB limit (`CONST_ROADMAP_PHASE_JSON_MAX_BYTES`). Counts give the result line and need no limit.
- **Run `staged_problems` in `publish`**: `src/devops_cli/roadmap/plan_check.py:547` adds the group size and the phrase rules, which none of the three checks of the agent runs, so a refusal there gives `plan_defect` until the split limit.
- **Have `publish` rewrite a long body with a model turn**: `publish` holds the App key and no model key after #6814, and the owner rule forbids a refusal for size. The fallback to the Why of `proposal.md` and then to the issue title needs no model.

## Production until #6814

| Form | Before #6814 | After #6814 | After the deletion item |
| :--- | :--- | :--- | :--- |
| `--phase all` (the default, no `--phase`) | CronJob `roadmap-stage` runs it. `run_stage_job` plans with the toolbox planner in one process, with the App key and the model key, and writes no run file. No change from `main`. | Nothing schedules it. It still runs `run_stage_job` for a person. | The deletion item decides. This plan proposes that the command then refuses `--phase all` with `--job-item`, because the only stage engine left has a shell. |
| `--phase prepare` | Runs only for a person or a test, with the App key. | The init container `prepare` runs it. | No change. |
| `--phase agent` | Runs only for a person or a test, with no GitHub credential. | The init container `agent` runs it, with the model key only. | No change. |
| `--phase publish` | Runs only for a person or a test, with the App key. | The container `publish` runs it. | No change. |

This pull request deletes no engine code. The follow-up item deletes it after a live Job of #6814 passes, and decides the other users of the toolbox: the fix-plan row, `devops roadmap step fix-plan`, the golden-set runs of `devops roadmap eval stage` and `devops roadmap eval verify`, and the round mode `devops roadmap stage --plan` and `--confirm` with no `--job-item`.

## The decisions of the old engine

| Decision | Where the old engine made it | Where it goes | Why |
| :--- | :--- | :--- | :--- |
| Selection, removals, orphans, rejections of other items (`read_stage_round`, `StageWriter.begin`) | before the model | `prepare` | GitHub and git only. |
| Rejection of the selected item (`StageWriter.settle`) | after the plan | `publish`, from the rejection in `state/` | It goes before the push of the item, as today. |
| Job-time premise (`_time_premise_of`) | before the first call | `prepare`, which returns the item to New | A GitHub read. A failed read fails the item with `ci_infra`, as on `main`. |
| False premise of the body probe (`probe_premise`, `_false_premise`) | before the first call | `prepare`, which returns the item to New | git only. |
| Blocker: a cited path that an open plan creates (`_dependency_of`, `open_plan_creates`) | before the first call | `prepare`, which returns the item to New | The store and git only. |
| Missing check that a reply claims (`_claim_premise`) | each reply | dropped | It judges model text. The review step reads each plan pull request (#6528, decision 4). |
| Kept plan file and its key (`PlanFiles`) | before the model | dropped from the phases | A Job pod has no volume of the Service, so a Job never hits a kept plan. The earlier plan stays readable on `origin/<branch>`. |
| Shadow tier choice of Jev (`_shadow_choice`) | before the model | dropped from the phases | A record of the tier of the old planner. |
| Request context with token caps (`_request`) | before the model | `prepare` writes the whole body and each comment, and the agent reads the repository itself | No cap that misses context. |
| Overlaps of open pull requests, files of named pull requests, titles of dependencies | before the model and in tools | #6831 | GitHub reads. The agent has no credential. |
| Tool budget and the end of the window (`stage_toolbox`) | model loop | dropped: the time budget only | No hard cap that fails a Job. |
| Schema retry of the reply (`parser`) | each reply | dropped | The agent writes Markdown, and the plan reader of the checks judges it. |
| Gates of each reply (`check_gates` with probes, overlaps, search evidence, citations, constants, the trace gate) | each reply | `RequireVerification` with the three checks, run again in `publish` | `plan-recheck` gives `check_gates` no probes, overlaps, search evidence or plan creates (`src/devops_cli/roadmap/plan_recheck.py`, module text). The gates that need the request or the trace of the toolbox go: the `Coder` run has no such trace. |
| Gate returns and the gate extension | each reply | the redirects of `RequireVerification` (`max_attempts`, 2) | Owner decision. |
| Degenerate reply stop (`_is_degenerate`) | each reply | the scaffold finding of `devops openspec check` | A marker of the scaffold of `prepare` stays until the agent replaces it. |
| Mechanical rewrite (`_rewrite_mechanical`) | each reply | dropped | A `rewrite` result of the folder fails `plan-recheck`, and the agent fixes its files. |
| Title (`staging_title`, `title_problems`) | each reply | `publish`, from the candidate, else from the summary of the issue title | The round leaves out an item whose summary does not fit, so the fallback fits. |
| Closing-keyword stop (`_stop_on_closing_keyword`) | each reply | `publish`, as `plan_defect` | Owner decision. A plan closes no issue. |
| Body form and the rewrite turn (`_plan_body`, `BodyReply`) | each reply | `publish` with `pull_request_body`, with the fallback to the Why of `proposal.md` and then to the issue title | `publish` has no model, and no size refusal fails a Job. |
| Measure of the groups and the split ask (`_fit`) | each reply | `publish` measures for the plan-state comment. The split ask goes. | The ask is a model call. |
| Budget stop (`OverBudget`, `_stop_on_budget`) | each reply | `publish`, unchanged: an owner question, no failure | Deterministic on the files. The inputs give the agent the step budget. |
| Restore of base scenarios (`_restored`) | each reply | dropped | A step of the render of a `StageProposal`. `openspec validate` judges the files of the agent. |
| Secret scan (`_assert_no_secrets`) | each reply | `publish`, before any push, as `plan_defect` | A security control. |
| File findings (`validate_change`, `staged_problems`) | each reply | `publish` runs the three checks. `staged_problems` stays with the CI job `Plan Check`. | See the rejected alternative. |
| Removal references and moved paths | after the plan | `publish` | git only, as warnings of the comment. |
| Model review, repair rounds, verify screen, findings, `verdict/fix-plan` | after the gates | dropped from the phases | #6528, decision 4: the review step gives each plan pull request its verdict. |
| Run trace and report (`RunTrace`, `_run_report`) | after the plan | counts in `outcome.json` | What passes holds only what `publish` reads. |
| Failure classes of the agent | errors of the run | one class of `plan_defect`, `timeout`, `provider`, `spend_limit` and `ci_infra`; `publish` refuses any other | The agent can end only with the classes that its own phase can raise. |
| Time budget stop (`RoadmapTimeBudgetError`) | before each call | a hook before each model request, with the end time of `prepare` and the deadline as cap | One budget for the Job. |
| Count of `plan_defect` and the return for a split (`plan_defects`, `check_in`) | check-in | the check-in of `publish`, unchanged | `SPLIT_CLASSES` holds `plan_defect`. |

## What prepare keeps

`prepare` writes `state/state.json`, which only `publish` reads:

- the repository, the item, the Job name and whether the check-out named the Job at the start;
- the target: the branch, the change folder, the draft that a re-stage replaces, the base (the tip of the default branch), the lease (the recorded `stage.sha` of a re-stage, the tip of the pushed branch, or empty) and the default branch;
- the date of the change, which the scaffold holds;
- the rejection of the selected item, if a person rejected its last plan;
- the paths that the open plans create, each with its item;
- the issue listing of `plan-recheck` (`state/issues.json`);
- the end time of the time budget and the GitHub requests that `prepare` sent;
- `ended` and the end, when `prepare` ended the run: the item is left out, the job-time premise or the body probe returned it to New, a blocker returned it to New, or a GitHub read failed. `prepare` then checks in, and the agent phase and `publish` write nothing new.

`prepare` writes the inputs of the agent in `work/`: `input.json` (the clone, the base, the default branch, the branch, the change folder, the date, the item number, title and body, every comment of a person with write access or of the App, the probe lines, the open-plan creates, the reason of a rejected plan, the step budget, the room of the body text, the end time of the budget and the branch of an earlier plan), a copy of the issue listing, and the clone with the scaffold.

## Texts

- The summary of the candidate reaches the title through `staging_title`, which calls `safe_title` once.
- The text of the candidate, the Why of `proposal.md` or the issue title reaches the body through `pull_request_body`, which calls `safe_text` once. `publish` masks the text first and calls `safe_text` no second time. A text that the form refuses gives the next text of the chain.
- The stage writer removes each control character other than the line feed from the body, the plan-state comment and the comment of the run.
- The stage writer cuts the plan-state comment and the comment of the run to 65536 characters, the limit of a GitHub comment. The plan files hold the full text.
- `outcome.json` holds no text. The failed checks are names of an enum, so no command text of the model reaches a comment.

## The agent and its checks

The agent is one `Agent` of pydantic-ai on the model of the task `stage`:

- `LocalWorkspace(<clone>)`;
- `Coder(instructions=<roadmap_stage_coder.md>, sub_agents=False)`, whose `Shell` leaf is the tool `run_command` with the time left of the budget as `default_timeout` and a scratch home, and whose context controls get the window of the task, as `_tune` of the implement step does;
- `RequireVerification(verification_commands=(<devops openspec check>, <openspec validate ... --strict>, <devops roadmap plan-recheck ... --branch HEAD>), exempt_paths=(), instructions=<the three commands>)`, in this order;
- `Hooks` with a listener of `CompletionUnverifiedEvent` and a time-budget check before each model request.

The prompt tells the agent to fill the scaffold, write the body candidate (`PLAN_PULL_REQUEST.md` at the root of the clone: a `# <summary>` line, then the what and the why), commit the change folder, and run the three checks: `devops openspec check`, `openspec validate <change> --strict` and `devops roadmap plan-recheck --source . --branch HEAD --issues <listing>`.

At the end, the agent phase writes `out/plan.patch` (the change folder only, from the base), `out/candidate.md` and `out/outcome.json`. A run that emitted `CompletionUnverifiedEvent` has the end `unverified` and the names of its failed checks. `publish` reads the outcome as data, checks in with the failure class `plan_defect`, exits 1 and pushes no branch. `plan_defect` counts toward `roadmap.stage.plan_defect_limit` on the body, as a refused plan does today.

## Tests

- Failing first: `tests/commands/test_roadmap_plan_recheck_cmd.py` (the fail rule and `--issues`), `tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_agent.py` (the capability list and the three patterns), `tests/roadmap/stage/test_roadmap_stage_agent_phase.py` (the credential refusal, the outcome, the unverified end), `tests/roadmap/stage/test_roadmap_stage_publish_checks.py` and `tests/roadmap/stage/test_roadmap_stage_publish.py`.
- One test for each rule of `publish`, with an output that breaks the rule: a path outside the change folder, a link, a secret, another date, a file that `devops openspec check` refuses, a file that `openspec validate` refuses, a folder that `plan-recheck` refuses, a closing keyword, an outcome with a key or a class outside its model, an outcome that says verified while a check fails, a patch over its limit of 16 MiB (`CONST_ROADMAP_PHASE_PATCH_MAX_BYTES`), and a state file of another item. Each ends with `plan_defect`, no push and exit 1. A candidate over its limit is no failure: the agent phase writes no candidate, and `publish` takes the next text of the chain.
- Equivalence: a stub agent writes the files that `--phase all` renders for one stub plan, and the separate phases push the same tree and write the same title, body, labels, record and comments. A second test runs the command with no `--phase` and finds `run_stage_job`, no state file and no outcome file.
- The tests of `run_stage_job` in `tests/roadmap/stage/test_roadmap_stage_job_entry.py` pass with no change.

## Pull requests

This item stays one pull request: the two options of `plan-recheck`, the three phases, the agent and the documents. The options of `plan-recheck` have no other user, and the phases cannot pass their tests without them. The deletion of the old engine needs a new item, because it can merge only after #6814 is live, and #6814 merges only after a release holds this change. #6831 follows this item and reuses the issue listing of `prepare`.

## Security

The change gives a coding agent a real shell. The shell runs only in the `agent` phase, which refuses to start with the App key, `GH_TOKEN`, `GITHUB_TOKEN` or a gh login, and whose shell gets a scratch home. `publish` holds the App key, runs no program of the clone, reads each output of the agent as data, refuses each path outside the change folder before it runs a check, and pushes with a lease from a new repository. A person must confirm that the agent container of #6814 holds no App key and reaches github.com only with no credential.
