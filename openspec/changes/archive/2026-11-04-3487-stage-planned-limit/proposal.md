# Proposal

## Why

Issue #3487: the stage job plans each item that its filter gives, and no limit stops it while the Planned queue grows. Plans merge faster than the Service delivers them. In the window 2026-11-03T15:05Z to 2026-11-04T15:05Z, 29 plan pull requests merged and the Service merged 2 delivery pull requests. At 15:06Z, 53 items were Planned, which is about 26 days of work for the Service at that rate. Each plan also takes the time of a person or an agent session: 25 of the 31 plan pull requests hold a correction commit. A plan that waits long meets a changed default branch, because 19 of 31 plans change `messages.py` and 17 change `stage_change.py`.

## What Changes

- The setting `roadmap.stage.planned_limit` (variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT`, default 20, at least 1) is the count of open Planned items at which the stage job plans no new item.
- The stage job leaves out each item with a reason when the count is at or over the limit. The reason names the count and the setting. An item with the priority `P0-Critical` passes the limit, and so does the item that `--item` names.
- `devops roadmap explain` shows that reason for an item that the limit holds, because it judges the item with the function that the job calls.
- `devops roadmap inbox` shows one line when the limit holds.
- The change adds a setting, a left-out reason and an inbox line, which a consumer observes, so it carries three spec deltas: one added requirement in each of `roadmap-stage`, `roadmap-explain` and `roadmap-inbox`.
- The change sets no limit on the filing of issues.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the setting and the rule of the limit.
- `roadmap-explain`: the reason of the limit for the stage job.
- `roadmap-inbox`: the line that states the limit.

## Impact

- `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- `tests/roadmap/test_roadmap_stage_selection.py`, `tests/roadmap/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/security/test_config_declarations.py`.
- `docs/roadmap/stage.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`, `k8s/devops/configmap.example.yaml`, and the generated documents.

## Feasibility

- `git grep -n "planned_limit\|max_planned"` on `origin/main` finds no limit on Planned items, and `gh` search of open issues for a Planned limit on the stage job finds only #3487. No newer item or code supersedes it.
- `select_stageable` (`src/devops_cli/roadmap/stage.py`) is the one function that `plan_stage` and `devops roadmap explain` call to select items, and `_Judge.reason` holds the left-out rules that `explain` reads. A rule in `_Judge` therefore reaches the job and the command with no second code path.
- `_open_items` already reads every open item, so the count of open Planned items needs no new request. `devops roadmap inbox` already reads the open items with `store.open_items()`.
- `CONST_ROADMAP_CRITICAL_PRIORITY` (`P0-Critical`) is the highest value of `CONST_ROADMAP_PRIORITY_VALUES`.
- The default 20 comes from the evidence in the issue: the Service merged 2 delivery pull requests a day, so 20 Planned items take about 10 days. A person can change the value with the setting.
- The limit holds back a round only at the start. A round can take up to `roadmap.stage.limit` items below the limit, so the count can pass the limit by less than that number. The design accepts this.

## Existing Tool Considered

`StageFilter`, the left-out reasons that `explain` reads, `priority_order` and `RoadmapStageConfig` cover the need. The change adds one setting, one rule in `_Judge` and one inbox line. It adds no tool and no library. #1127 can later propose groups of items.
