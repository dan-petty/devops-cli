# Proposal

## Why

The Service created one implement Job per repository at a time. A queue of planned items emptied slowly at one item per 8 to 18 minutes. #3064 asks one round to fill several slots with items whose plans change disjoint files. The per-item claim, Job label, GitHub request budget, and model lane limits stay the rule.

## What Changes

- The implement round reads the setting `roadmap.implement.max_parallel_jobs` (default 1). It counts running Jobs of its repository against it.
- A new module `src/devops_cli/roadmap/implement/implement_parallel.py` computes change sets from `Changes:` lines, capability specs, and generated documents. It decides whether two items conflict.
- The round filters out items already held by running Jobs or claims before applying free slots.
- The round selects up to `slots` targets that do not conflict with each other or running Jobs.
- An item whose plan names no change file, or whose group line the reader refuses, runs alone in its round.
- The runner Job carries the item label beside the repository label. The round skips an item that a running Job holds.
- Each runner Job enforces `set_model_call_limit(1)` and installs a per-job `RequestBudget`.
- The round checks cluster capacity: it creates no new Job while any running runner pod is in a Pending state.
- `SubmitResult.created` holds a tuple of Job names, and the round logs all created Jobs.
- A test using `git_for_real` in `tests/roadmap/implement/test_implement_parallel.py` proves that disjoint branches merge cleanly and overlapping capability specs conflict.
- `uv run devops docs generate` writes the setting into generated docs. `docs/CLUSTER.md` and `CONTEXT.md` document the setting and disjoint-file rules.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/runner-job`: The parallel limit is a setting, An item with a claim or a labelled Job gets no second Job, The Service submits implement Jobs for the disjoint items of one repository
- `roadmap-implement-job/selection`: The round takes only items whose change files are disjoint, An item with no change set runs alone

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/implement/implement_parallel.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/run.py`
- Documents: `docs/CLUSTER.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `CONTEXT.md`
- Tests: `tests/security/test_config_declarations.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/implement/test_implement_parallel.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- The probes confirm cited modules: `src/devops_cli/roadmap/implement/implement_submit.py` and `src/devops_cli/config/defaults.py` exist.
- `roadmap.implement.max_parallel_jobs` is a new setting name.
- The round waits while any Job runs (`src/devops_cli/roadmap/implement/implement_submit.py:546`).
- `DEFAULT_ROADMAP_IMPLEMENT_LIMIT` is 1 (`src/devops_cli/config/defaults.py:1026`). The new setting keeps that default.
- `group_files` reads code spans of `Changes:` lines (`src/devops_cli/roadmap/plan_read.py:381`).
- The item label exists for stage Jobs (`src/devops_cli/k8s/cluster_job.py:40:ITEM_LABEL`). The implement Job now adds it.
- `ClusterJob.started` is None when a pod is Pending. The scheduler checks this field before creating more Jobs.
- `install_request_budget` and `set_model_call_limit(1)` bound GitHub requests and model concurrency.
- `git_for_real` runs git in tests (`tests/support/implement_step.py:142`). Tests run in a temporary directory with no network.
- The first checks of the implementation against the real system: `uv run devops ci test tests/roadmap/implement/test_implement_parallel.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py`, and `uv run devops ci docs`.

## Existing Tool Considered

Hatchet (MIT, maintained) covers concurrency limits and rate limits. It does not compute disjoint file sets or capability spec overlap. The custom scheduler stays in the Service.

## Dependencies

None.
