# Proposal

## Why

The Service created one implement Job per repository at a time, so a queue of 29 planned items emptied at one item per 8 to 18 minutes. #3064 asks one round to fill several slots with items whose plans change disjoint files, while the per-item claim, the Job label, the GitHub request budget and the model lane stay the rule.

## What Changes

- The implement round reads the setting `roadmap.implement.max_parallel_jobs` (default 1) and counts the running Jobs of its repository against it, as the stage row counts `roadmap.stage.jobs`.
- A new module `src/devops_cli/roadmap/implement/implement_parallel.py` reads the `Changes:` paths of a plan with `group_files` and decides whether two items conflict, a shared path and a parent-child pair included.
- The round plans with the free slots, takes the targets in the order of the plan, and creates one Job for each target that conflicts with none of the taken ones.
- An item whose plan names no change file, or whose group line the reader refuses, runs alone in its round.
- The runner Job carries the item label beside the repository label, and the round skips a target whose item label a running Job of the repository holds.
- A create that the API refuses keeps today's handling: the record and the claim go back and the error raises, so the item is eligible in the next round.
- A test that runs real git through `git_for_real` on a repository under `tmp_path` proves that two branches of disjoint files merge with no conflict.
- The change adds no ResourceQuota manifest: namespace `devops` holds none today, and the API server's answer to the create stays the only cluster check the round makes.
- The change adds no RBAC rule and no new host: each Job keeps the installation token of one repository.
- `uv run devops docs generate` writes the setting into the generated `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`, and `docs/CLUSTER.md` names the setting and the disjoint-file rule.
- `CONTEXT.md` states the per-item Job rule and the disjoint-file rule in the Runner term.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/runner-job`: The parallel limit is a setting, An item with a claim or a labelled Job gets no second Job, The Service submits implement Jobs for the disjoint items of one repository
- `roadmap-implement-job/selection`: The round takes only items whose change files are disjoint, An item with no change set runs alone

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/implement/implement_parallel.py`, `src/devops_cli/roadmap/implement/implement_submit.py`
- Documents: `docs/CLUSTER.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `CONTEXT.md`
- Tests: `tests/security/test_config_declarations.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/roadmap/implement/test_implement_parallel.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_implement_parallel_merge.py`

## Feasibility

- The probe says the cited module is a file of the staging commit: "The path `src/devops_cli/roadmap/implement/implement_submit.py` is a file of the staging commit."
- The probe says the cited defaults module is a file too: "The path `src/devops_cli/config/defaults.py` is a file of the staging commit."
- The setting is a name to create, not a false premise: "The path `roadmap.implement.max_parallel_jobs` is no file of the staging commit. No commit in the history deleted or renamed it."
- The premise of the issue holds: the round waits while any Job of the repository runs (`src/devops_cli/roadmap/implement/implement_submit.py:546:` `if any(job.state is JobState.RUNNING for job in held.values()):`) and repeats the wait before the create (`src/devops_cli/roadmap/implement/implement_submit.py:563:` `if _runs(api, label):`).
- The round plans with the limit 1 (`src/devops_cli/roadmap/implement/implement_submit.py:555:` `limit=DEFAULT_ROADMAP_IMPLEMENT_LIMIT,`) and creates the Job of the first selected item only (`src/devops_cli/roadmap/implement/implement_submit.py:571:` `number = plan.selected[0].item.number`).
- The staged constant that the round uses today: `DEFAULT_ROADMAP_IMPLEMENT_LIMIT` has the value 1 (`src/devops_cli/config/defaults.py:1026:` `DEFAULT_ROADMAP_IMPLEMENT_LIMIT: int = 1`), and the new setting keeps that default, so a configuration with no value behaves as it does today.
- The reader that the change reuses: `src/devops_cli/roadmap/plan_read.py:381:` `def group_files(text: str) -> GroupFiles:` reads the code spans of the `Changes:` half of a group, and it raises when a group holds no such line (`src/devops_cli/roadmap/plan_read.py:386:` `raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_tasks)`), which the new predicate turns into an empty set.
- `parse_task_groups` splits a tasks file into groups (`src/devops_cli/roadmap/step_files.py:171:` `def parse_task_groups(tasks_md: str) -> list[TaskGroup]:`), and `StageGroup` holds the `changes` field that the plan check reads (`src/devops_cli/roadmap/stage/stage_change.py:class StageGroup`).
- The round already reads the tasks of a target for its size (`src/devops_cli/roadmap/implement/implement_submit.py:441:` `tasks = tasks_at(Path(source), rev, target.item.number, operation=GIT_OPERATION)`), so one read gives both the size and the change set.
- The item label exists for the stage Job (`src/devops_cli/k8s/cluster_job.py:40:` `ITEM_LABEL = "roadmap.devops-cli/item"`), and the stage round reads it (`src/devops_cli/roadmap/stage/stage_submit.py:249:` `if job is not None and job.labels.get(ITEM_LABEL) != str(item.number):`); the implement Job carries the repository label only (`src/devops_cli/roadmap/implement/implement_submit.py:477:` `labels={CONST_ROADMAP_IMPLEMENT_JOB_LABEL: label},`).
- The claim already refuses a second Job for an item (`src/devops_cli/roadmap/implement/implement_submit.py:469:` `if not service_claim(store, number, marks):`), and a failed create takes the record and the claim back before it raises (`src/devops_cli/roadmap/implement/implement_submit.py:488:` `service_release(store, number, {ImplementRecordKey.JOB: None})`), so the item is eligible in the next round with no new code.
- The review finding is right and the plan now carries no quota premise: namespace `devops` holds no ResourceQuota (`openspec/changes/archive/2026-11-12-4939-searxng-worker-memory/proposal.md:19:` `has no ResourceQuota or LimitRange`), the archive records the same for Jobs (`openspec/changes/archive/2026-11-13-5483-stage-job-template-entry/design.md:15:` `No ResourceQuota in namespace`), and `list_files` of `k8s/devops` shows no ResourceQuota manifest. So the change adds no requirement that a quota bounds the Jobs and adds no manifest; the cluster check of the issue is the API server's answer to the create, and a real quota needs its own change because a fixed bound counts the Service's own pods and the runner Job size varies with the plan.
- The row runs the round for one repository (`src/devops_cli/roadmap/run.py:820:` `result = run_implement_round(store, repo=repo, source=source)`), so the limit is per repository and needs no global count, and the stage row already fills several slots from a setting (`src/devops_cli/roadmap/stage/stage_submit.py:359:` `slots = max(load_settings().roadmap.stage.jobs - len(running) - elsewhere, 0)`).
- The merge proof runs real git as the implement tests already do: `git_for_real` runs the call (`tests/support/implement_step.py:142:` `def git_for_real(call: ProcessCall) -> subprocess.CompletedProcess[str]:`), and a planned-item test installs it on `process_fake` (`tests/roadmap/implement/test_roadmap_implement_planned.py:481:` `process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))`).
- Precondition of `plan_implement`: a checkout of the repository, a client of the GitHub service and a network, because it reads the checkout, the remote heads, the planned changes and the GitHub session.
- Precondition of `tasks_at` and `tasks_on_default`: a checkout of the repository, because each reads a file of a commit with git.
- Precondition of `service_claim` and `service_release`: a client of the roadmap store, which is GitHub.
- Precondition of `ClusterJobs.list_jobs`, `ClusterJobs.cronjob` and `ClusterJobs.create`: a client of the Kubernetes API and a network to the API server.
- Precondition of `run_subprocess` in the merge test: no checkout, no client and no network, because git runs in a repository under `tmp_path` with no remote.
- No command or verify program is new: `uv run devops ci test` and `uv run devops ci docs` exist, `devops` and `git` are in the runner image, and no pod setting changes.
- The new guard covers the `Changes:` paths of the plans that the round selects at run time and no set of the repository, so no census applies.
- The context lists no overlap and no metric sender, so the plan has no dependency entry.
- The plan moves and renames no module, so it needs no references entry; it deletes the private `_runs` (`src/devops_cli/roadmap/implement/implement_submit.py:516:` `def _runs(api: ClusterJobs, label: str) -> bool:`), whose only caller is the wait at line 563.
- The first checks of the implementation against the real system: `uv run devops ci test tests/roadmap/implement/test_implement_parallel.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py`, and `uv run devops ci docs`.

## Existing Tool Considered

Hatchet (MIT, maintained) covers a configurable concurrency limit, round-robin concurrency groups and rate limits. It reads no plan, computes no disjoint file set, proves no merge and bounds no namespace, so the plan-aware predicate stays in the Service: about 150k tokens and 24 hours to build, and 30k tokens per year to keep and fix.

## Dependencies

None.
