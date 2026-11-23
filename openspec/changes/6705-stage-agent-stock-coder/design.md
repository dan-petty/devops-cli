# Design

## Decisions

- **`--phase all` keeps `run_stage_job` and its writer in one process until #6814 is live.**: CronJob `roadmap-stage` runs one container with the App key and the model key (`k8s/devops/cronjob-stage.yaml:86`). The Service passes no `--phase` (`src/devops_cli/roadmap/stage/stage_submit.py:325`), and the owner asked for one process with no result file.
- **The `Coder` agent runs only in a separate `agent` phase.**: That phase refuses the App key, each GitHub token variable and a gh login, so its shell reaches no GitHub credential.
- **The agent uses the shell of `Coder` as it is.**: The owner kept the stock persistent shell. `Coder` 0.71.0 builds it with `default_timeout=MAX_FOREGROUND_WAIT`, which is 270 s (`coder/_capability.py:294-300`).
- **`LocalWorkspace` gets a scratch home and `DEVOPS_CLI_CONFIG`.**: `LocalWorkspace` passes only `PATH`, `HOME`, `LANG`, `LC_ALL` and `LC_CTYPE` to a command. With the configuration file, the checks of the agent read the settings that `publish` reads, such as `roadmap.stage.step_tokens`.
- **`plan-recheck --base` judges only the folders that the branch changes from the base of `prepare`.**: It makes no fetch and reads no ref of the default branch, so a merge during the run changes no result. It judges one folder, so it is fast.
- **`plan-recheck --base` also runs the plan-check rules, the scan of removal references, and the title and body rules.**: The owner asked that the model sees these rules in the same run. `--candidate` gives the body candidate, and the command builds the title and the body as `publish` does.
- **`RequireVerification` steers the agent, and the rerun of `publish` is the gate.**: The capability counts a run as verified when one check ran after the last edit and each recorded check passed (`require_verification/_capability.py:281`). So a run with one of the three checks passes it.
- **`publish` trusts no end that the agent reports.**: It reads the outputs as data and accepts `timeout` only after the end time of `state/`. Its own checks decide each other end, `unverified` included.
- **`publish` has one push: the writer calls `publish_patch`, with the checks in `before_push`.**: The checks judge the tree that the push sends. A plan that a check refuses makes no push.
- **A fixed list of findings is `ci_infra`, and each other finding is `plan_defect`.**: `ci_infra` takes only the gate checks `version`, `configuration`, `skills` and `instructions`, a missing tool, and a network or GitHub error. A guess from the text of a finding could hide a plan defect and run the Job again with no limit.
- **A plan whose only finding is `group-over-budget` stops with `_stop_on_budget`, as on `main`.**: The agent sees the size rule and splits the group. A group that stays over the budget asks the owner, and records no failure (`src/devops_cli/roadmap/stage/stage.py:4103`).
- **`publish` counts an `ci_infra` end of the agent toward `roadmap.stage.plan_defect_limit`, in `stage_job_phases.py` only.**: The agent can cause that end, for example with a broken `.git`. `provider` and `spend_limit` keep their waits and no count, because a split does not help an outage.
- **`publish` cleans each text and fits each comment before it calls the writer of `--phase all`.**: The writer stays as it is, so `--phase all` writes the same comments as on `main`.
- **`publish` gives the writer a clone of its own, at the base of `prepare`.**: The writer runs git in its source, and the clone under `work/` belongs to the agent.
- **`prepare` commits the scaffold of the change folder.**: The commit holds the date of `prepare`, so `plan-recheck --base` judges the scaffold from the first check.
- **The issue listing holds `IssueRecord` entries for the recheck only.**: Each record has the number, the title, the URL and the state. Only the record of the item holds its body.
- **The agent run has no request limit, and `repo_context=False`.**: The time budget of the Job is the only bound. The prompt holds the plan rules that `test_roadmap_stage_prompt_rules.py` checks, as the implement step does (`src/devops_cli/roadmap/implement/implement_step.py:806`).

## Rejected alternatives

- **Run the `Coder` agent in `--phase all`**: `k8s/devops/cronjob-stage.yaml:105` gives the one container the App key, so the shell would run next to it in production until #6814.
- **Delete the old engine in this pull request**: `--phase all` needs `run_stage_job` until #6814 is live, and `src/devops_cli/roadmap/run.py:815` uses the toolbox outside the stage Job. #6846 does it.
- **The tool `run_command` in place of `shell`**: the owner kept the stock shell. A check that a real checkout measures over 270 s brings the question back to the owner.
- **Compare the branch with `origin/<default>`**: `src/devops_cli/roadmap/planned.py:98` fetches it on each run, and the review of #6841 counted 26 of 33 folders there as not `ok`. A merge during a run would fail a plan that the agent cannot fix.
- **Read the default branch from `refs/remotes/origin/HEAD` with a base**: the repository of `publish_patch` has no `origin/HEAD`, so `default_branch` (`src/devops_cli/roadmap/clone_git.py:56`) exits 128 there. The caller gives the default branch with the base.
- **Run `staged_problems` in `publish` only**: `src/devops_cli/roadmap/plan_check.py:547` adds the group size, the phrase rules and the title and body rules. The agent would not see a refusal of them, and the item would end in `plan_defect` until the split limit.
- **Class a finding as `ci_infra` when it names no file of the change folder**: `openspec validate` names the change and the capability, and the overlap gate names changes (`src/devops_cli/openspec/gate.py:181`). That rule would class plan defects as `ci_infra`, which retries with no limit.
- **Count each end that the agent reports toward the split limit**: an outage of the provider, GitHub or the cluster does not count, by owner rule (`src/devops_cli/roadmap/stage/stage_job.py:35`). A split does not help it.
- **Change `SPLIT_CLASSES` or `check_in` for the count of the agent**: the Service and `--phase all` read both, so production would change.
- **Trust the end that the agent reports**: an agent can break its own `.git` and report `ci_infra`, which retries, or report `timeout` early.
- **Run `bootstrap_checkout` in `prepare`**: the stage Job runs no bootstrap by design (`k8s/devops/cronjob-stage.yaml:88`). A bootstrap would install packages from the registry for each Job, and `publish` would need a second one.
- **Clean and cut the comments in the shared writer**: `_stage_one` (`src/devops_cli/roadmap/stage/stage.py:4001`) writes the comments of `--phase all`, so production would change before #6814.
- **Give the writer the clone under `work/`**: the agent can write the git configuration and the hooks of that clone. The writer runs git in it (`src/devops_cli/roadmap/stage/stage.py:4021`).
- **The whole issue listing in `state/`**: it is 11,291,737 bytes for 828 issues, and the limit of a run file is 1 MiB (`src/devops_cli/config/constants.py:3885`).
- **`AgentOutcome` of `src/devops_cli/roadmap/phases/files.py:106` for the outcome**: its `result`, `reason` and `counts` map hold text and free keys. `StageOutcome` holds an enum and fixed fields.
- **`PhaseOutputError` for a refused plan**: it maps to `ci_infra` (`src/devops_cli/roadmap/failure.py:183`), so a refused plan would run again and again. So does `PublishRefusedError`, which `publish` catches as `plan_defect`.
- **A trace of the agent in `outcome.json`**: the trace of PR #6822 kept tool answers and had to stay under 1 MiB. Fixed count fields give the result line with no limit.
- **Have `publish` rewrite a long body with a model turn**: `publish` holds no model key after #6814, and the owner rule forbids a refusal for size.

## Production until #6814

| Form | Before #6814 | After #6814 | After #6846 |
| :--- | :--- | :--- | :--- |
| `--phase all` (the default) | CronJob `roadmap-stage` runs it: `run_stage_job` with the toolbox planner and the writer of `main`, in one process, with no run file. | Nothing schedules it. It runs `run_stage_job` for a person. | #6846 refuses `--phase all` with `--job-item`. |
| `--phase prepare` | A person or a test runs it, with the App key. | The init container `prepare` runs it. | No change. |
| `--phase agent` | A person or a test runs it, with no GitHub credential. | The init container `agent` runs it, with the model key only. | No change. |
| `--phase publish` | A person or a test runs it, with the App key. | The container `publish` runs it. | No change. |

This pull request changes no behavior of `--phase all`. The shared parts get only a seam that `--phase all` does not use: the push of `_stage_one` is an argument whose default is `push_plan`.

## The decisions of the old engine

| Decision | Where the old engine made it | Where it goes | Why |
| :--- | :--- | :--- | :--- |
| Selection, removals, orphans, rejections of other items | before the model | `prepare` | GitHub and git only. |
| Rejection of the selected item | after the plan | `publish`, from the rejection in `state/` | It goes before the push, as today. |
| Job-time premise | before the first call | `prepare`, which returns the item to New | A failed read fails the item with `ci_infra`, as on `main`. |
| False premise of the body probe | before the first call | `prepare`, which returns the item to New | git only. |
| Blocker: a cited path that an open plan creates | before the first call | `prepare`, which returns the item to New | The store and git only. |
| Missing check that a reply claims (`_claim_premise`) | each reply | dropped | It judges model text. The review step reads each plan (#6528, decision 4). |
| Kept plan file and its key | before the model | dropped from the phases | A Job pod has no volume of the Service. The earlier plan stays on `origin/<branch>`. |
| Shadow tier choice of Jev | before the model | dropped from the phases | A record of the tier of the old planner. |
| Request context with token caps | before the model | `prepare` writes the whole body and each comment | No cap that misses context. |
| Overlaps, files of named pull requests, titles of dependencies | before the model | #6831 | GitHub reads. The agent has no credential. |
| Tool budget and the end of the window | model loop | dropped: the time budget only | No hard cap that fails a Job. |
| Schema retry of the reply | each reply | dropped | The plan reader of the checks judges the Markdown of the agent. |
| Gates of each reply | each reply | `RequireVerification` with the three checks, run again in `publish` | The gates that need the request or the trace of the toolbox go. |
| Gate returns and the gate extension | each reply | the redirects of `RequireVerification` (`max_attempts`, 2) | Owner decision. |
| Degenerate reply stop | each reply | the scaffold finding of `devops openspec check` | A marker of the committed scaffold stays until the agent replaces it. |
| Mechanical rewrite | each reply | dropped | A `rewrite` result fails `plan-recheck --base`, and the agent fixes its files. |
| Title and body rules | each reply | `plan-recheck --base --candidate`, run again in `publish` | One builder for the agent and for `publish`. |
| Closing-keyword stop | each reply | `plan-recheck --base --candidate`, and `publish` as `plan_defect` | A plan closes no issue. |
| Body rewrite turn | each reply | dropped: a fallback chain in the builder | `publish` has no model, and no size refusal fails a Job. |
| Measure of the groups and the split ask | each reply | the size rule of `plan-recheck --base`; the ask goes | The agent splits the group in the same run. |
| Budget stop (`OverBudget`) | each reply, before the file findings | `publish`: a plan whose only finding is `group-over-budget` stops with `_stop_on_budget` | An owner question and no failure, as on `main`. |
| Restore of base scenarios | each reply | dropped | `openspec validate` judges the files of the agent. |
| Secret scan | each reply | `publish`, before any push, as `plan_defect` | A security control. |
| File findings (`validate_change`, `staged_problems`) | each reply | `openspec validate` and the plan-check rules in `plan-recheck --base` | The agent sees each rule that `publish` runs. |
| Removal references (`_check_removal_references`) | after the plan | a test reference: `plan-recheck --base` refuses it. A source reference: a warning of the comment. | The old engine raised for a test reference (`src/devops_cli/roadmap/stage/stage.py:1301`). |
| Moved paths | after the plan | `publish`, as warnings of the comment | git only. |
| Model review, repair rounds, verify screen, `verdict/fix-plan` | after the gates | dropped from the phases | The review step gives each plan its verdict. |
| Run trace and report | after the plan | fixed count fields of `StageOutcome` | What passes holds only what `publish` reads. |
| Failure classes | errors of the run | see "The ends of a run" | `publish` trusts no end that the agent reports. |
| Time budget stop | before each call | a hook before each model request, with the end time of `prepare` | One budget for the Job. |
| Count of `plan_defect` and the return for a split | check-in | the check-in of `publish`, plus the `ci_infra` ends of the agent | `SPLIT_CLASSES` and `check_in` stay as they are. |

## What prepare keeps

`prepare` writes `state/state.json`, which only `publish` reads, under the limit of 1 MiB:

- the repository, the item, the Job name and whether the check-out named the Job;
- the target: the branch, the change folder, the draft that a re-stage replaces, the base, the lease and the default branch;
- the date of the change, which the committed scaffold holds;
- the rejection of the selected item, if a person rejected its last plan;
- the paths that the open plans create, each with its item;
- the end time of the time budget and the GitHub requests that `prepare` sent;
- `ended` and the end, when a decision of `prepare` ended the run.

`state/issues.json` is the issue listing, a list of `IssueRecord`, also under 1 MiB. Each record holds the number, the title, the URL and the state. The record of the item also holds its body. The listing holds the item and each issue that an active folder of the base names. GitHub limits a body to 65,536 characters, so the body takes at most 262,144 bytes.

The inputs of the agent are in `work/`: `input.json`, a copy of the listing, and the clone with the scaffold commit. `input.json` holds these values:

- the base, the default branch, the branch, the change folder and the date;
- the item and each comment of the item;
- the probe lines, the open-plan creates and the reason of a rejected plan;
- the step budget, the room of the body text and the end time of the budget.

## Texts

- A new module, `stage_candidate.py`, builds the title and the body from the candidate. `plan-recheck --base` and `publish` both call it.
- The summary of the candidate reaches the title through `staging_title`, which calls `safe_title` once.
- The text of the candidate, else the Why of the proposal, else the issue title, reaches the body through `pull_request_body`. That function calls `safe_text` once, and the builder only masks the text before it.
- A closing keyword in the summary or the text is a finding of the check, and `plan_defect` in `publish`.
- `publish` removes each control character other than the line feed from each text that it hands to the writer. These are the title, the body, the group titles and the warnings.
- `publish` measures the plan-state comment with the function of the writer. When it is over 65,536 characters, `publish` cuts the group titles of that comment. The plan files keep the full titles.
- `StageOutcome` holds no text, so no command text of the model reaches a comment.

## The agent and its checks

The agent is one pydantic-ai `Agent` on the model of the task `stage`:

- `LocalWorkspace(<clone>, env=...)`, whose `env` holds a scratch `HOME`, `DEVOPS_CLI_CONFIG`, `GIT_CONFIG_NOSYSTEM=1` and `GIT_TERMINAL_PROMPT=0`;
- `Coder(instructions=<roadmap_stage_coder.md>, repo_context=False, sub_agents=False)`, with its shell as it is and its context controls on the window of the task;
- `RequireVerification` with `exempt_paths=()`, instructions that name the three commands, and three patterns in this order;
- `Hooks` with a listener of `CompletionUnverifiedEvent` and a check of the time budget before each model request.

The patterns match `devops openspec check`, `openspec validate ... --strict`, and `devops roadmap plan-recheck` with `--branch HEAD`, `--base <sha>` and `--candidate <file>`.

The prompt gives the full commands. It tells the agent to fill the scaffold, write `PLAN_PULL_REQUEST.md` at the root of the clone, commit the folder and run the checks. A finding of the environment is no fault of the plan, and the agent says so and ends.

## The ends of a run

The agent phase writes `out/plan.patch` (the change folder from the base), `out/candidate.md` and `out/outcome.json`. The outcome is `StageOutcome`, a new model. It holds the end and the names of the failed checks as an enum. Its fixed count fields are `requests`, `tool_calls`, `input_tokens`, `output_tokens` and `seconds`.

| End in the outcome | What `publish` does |
| :--- | :--- |
| `ended` or `unverified` | Its own checks decide, in `before_push`. No finding: the push goes. Only `group-over-budget`: `_stop_on_budget`. A finding of the `ci_infra` list only: `ci_infra`. Any other finding: `plan_defect`. |
| `timeout` | It accepts the end only after the end time of `state/`, and checks in `deadline` with exit 143. Before that time, it treats the end as `ended`. |
| `provider` or `spend_limit` | It records the class with its wait, and the end does not count toward the split limit. |
| `ci_infra` | It records the class with its wait. The end counts toward `roadmap.stage.plan_defect_limit`, and the end that reaches the limit is `plan_defect`. |
| no outcome, or an outcome outside its model | `plan_defect`. |

The `ci_infra` list of `publish` is fixed. It holds the gate checks `version`, `configuration`, `skills` and `instructions`, a missing tool (`DependencyError`), and a network or GitHub error. Each other finding, each other tool error and `PublishRefusedError` is `plan_defect`.

`publish` writes the count of a `ci_infra` end of the agent with `plan_defects` in the marks of `check_in`. At the limit, it ends the run as `plan_defect`, so `check_in` returns the item for a split as today. This changes the text of `docs/roadmap/stage.md` (the paragraph on the classes), the description of `roadmap.stage.plan_defect_limit` in `src/devops_cli/config/settings.py`, `docs/ENV_VARS.md`, and the module text of `src/devops_cli/roadmap/stage/stage_job.py`.

A SIGTERM in the agent phase writes no check-in. The Service checks in for the Job, as `stage_submit.py` does today.

## Tests

- Failing first, in these files: `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_agent.py`, `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`, `tests/roadmap/stage/test_roadmap_stage_publish_checks.py`, `tests/roadmap/stage/test_roadmap_stage_publish.py` and `tests/roadmap/stage/test_roadmap_stage_job_entry.py`.
- One test for each rule of `publish`, each with an output that breaks the rule.
- A run of `recheck_plans` with a base in a repository that is made as `publish_patch` makes one, with no `origin/HEAD`.
- A run of `plan-recheck --base` with an `origin` that refuses each fetch.
- An issue listing of a store whose issues hold more than 1 MiB.
- `publish` runs no git command under `work/`.
- `publish` counts the requests of `prepare`.
- A SIGTERM in the agent phase writes no check-in.
- The agent phase refuses an `out/` that is there before it.
- Equivalence: a stub agent writes the files that `--phase all` renders for one stub plan. With a fixed commit time, the separate phases push the same tree and `stage.sha`, and write the same title, body, labels, record and comments.
- The tests of `run_stage_job` in `tests/roadmap/stage/test_roadmap_stage_job_entry.py` and of the writer in `tests/roadmap/stage/test_roadmap_stage_apply.py` pass with no change.

## Pull requests

This item stays one pull request: the options of `plan-recheck`, the three phases, the agent and the documents. The options have no other user, and the phases cannot pass their tests without them. #6846 deletes the old engine after #6814 is live. #6831 follows this item and builds on the issue listing of `prepare`.

## Security

The change gives a coding agent a real shell. The shell runs only in the `agent` phase. That phase refuses the App key, `GH_TOKEN`, `GITHUB_TOKEN` and a gh login, and its shell gets a scratch home. `publish` holds the App key and runs no program of the clone. It reads each output of the agent as data and allows only the files of a plan before it runs a check. It writes from a clone of its own and pushes with a lease from a new repository. A person must confirm that the agent container of #6814 holds no App key.
