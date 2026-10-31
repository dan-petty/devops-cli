# Proposal

## Why

Issue #2906. The default filters of the stage job and of the implement job name Ready P0 and P1 bugs. The stage job staged every Ready P0 and P1 bug. The implement job delivered two of them. The two that remain are `effort/medium`, so the implement filter leaves them out. All other Ready items wait, because both filters name bugs of P0 and P1 only. On 2026-10-31 the owner decided: the stage job plans every Ready item, and the implement job implements every Ready item of low effort.

## What Changes

- `DEFAULT_ROADMAP_STAGE_FILTER` in `config/defaults.py` is `status=ready` alone. The job plans a Ready item of any type, priority, value and effort. `limit` (3 a round) and `step_tokens` do not change.
- `DEFAULT_IMPLEMENT_FILTERS` in `roadmap/implement.py` is `status=ready` and `effort=low`. The job implements a Ready item of low effort, of any type, priority and value.
- The example ConfigMap `k8s/devops/configmap.example.yaml`, the help texts, the module texts, `docs/CONFIGURATION.md` and the generated documents name the new defaults.
- The specs `roadmap-stage` and `roadmap-implement-job` carry the new defaults.
- The order of selection does not change. Both jobs sort the items that the filter names by priority, P0 first, and then by issue number, lowest first (`stage.priority_order`). An item with no priority goes last. A test holds that a P0 item goes before a P3 item.
- The live ConfigMap changes when the owner syncs it. This change does not touch the cluster.
- A consumer observes the defaults of a command and of a setting, so the change carries a spec delta.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the default filter and the default setting name every Ready item.
- `roadmap-implement-job`: the default filter names every Ready item of low effort.

## Impact

- `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/stage.py` (module text), `src/devops_cli/lang/en/help.py`, `k8s/devops/configmap.example.yaml`.
- `tests/roadmap/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_stage_selection.py`, `tests/roadmap/test_roadmap_implement_selection.py`, `tests/k8s/test_k8s_configmap.py`.
- The documents that `devops docs generate --sync-readme` writes.

## What the wider filter touches

Before, both jobs touched Ready P0 and P1 bugs. Now they touch every Ready item. On 2026-10-31 more than 80 Ready items exist. They are bugs, features, refactors, tests, docs items, chores and `type/infra` items with the title types `perf`, `build` and `ci`, of priority P1 to P3. No open issue has the label `type/epic`. The jobs do not read `type/*` labels to build anything. They read the Conventional Commit type of the title, and the other checks of the jobs do not depend on a bug:

- **Branch and title.** `stage._target_of` takes the type from the title of the issue (`commit_title.commit_type`), and `branch_name` makes `<type>/<issue>-<slug>`. `delivery_title` keeps the type and the scope of the issue title. So a feature gets `feat/…`, a docs item `docs/…`, a test item `test/…`. The staging pull request has the type `docs(openspec)` for every item. A title with no type is left out of both jobs with a reason (`_Judge._title`, `implement.py`).
- **Closing text.** `implement_pull_body` is `Closes #<issue>` for every item. The staging body is `Plans #<issue>` for every item.
- **Prompts.** The stage prompt `roadmap_stage_change.md` and the step prompt `roadmap_implement_step.md` hold the word "bug" nowhere. They ask for a failing test first for every item, which AGENTS.md rule 4 asks for every change. A docs item gets a test that the docs check holds, as the project does for other docs changes.
- **The fix step.** `implement_step_fix` is the name of the step that repairs a failed check. It is no type.
- **Checks.** `uv run devops ci` runs for every type. The step runs the verification command of the group.
- **Security items.** The job opens a draft pull request. Only a person merges it. The step shell runs only git, uv, ruff and mypy in a runner pod, so it cannot change a secret, a host or the cluster. The label rules of #2846 (declared scopes only) work on the title scope, not on a type.
- **Cost.** The stage job takes at most 3 items a round, every 60 minutes. With a wide filter it uses the model more often than before. The implement job still takes one item a round. This is the owner's decision.
- **Medium and high effort.** The stage job plans them. The implement job leaves them Staged until a person starts the work, as it did with #2147 and #2747.

## Feasibility

Confirmed on 2026-10-31 against the real system.

- **Current state.** `uv run devops roadmap stage --plan` on `main` lists only #2147 and #2747 as left out, because their plans are on `main`. It lists no other item, though more than 80 Ready items exist. `uv run devops roadmap implement --plan` prints "No item to implement". That is the problem of the issue.
- **Where the defaults are set.** `DEFAULT_ROADMAP_STAGE_FILTER` (`config/defaults.py`) is the default of the setting `roadmap.stage.filter` (`config/settings.py`). `DEFAULT_IMPLEMENT_FILTERS` (`roadmap/implement.py`) is the only default of the implement filter. No setting names it, and `k8s/devops/configmap.example.yaml` has no implement key. `implement_submit.py` calls `parse_implement_filters(())` for the Service round. So the implement default is set in code only, and the ConfigMap needs a change for the stage filter only.
- **Selection order.** `select_stageable` and `plan_implement` sort with `stage.priority_order`: the rank in `CONST_ROADMAP_PRIORITY_VALUES`, then the issue number. A P0 item goes before a P3 item.
- **The type of a branch.** The stage plan and the implement plan make the branch from the title (`stage._target_of`, `implement.py` line 247). A test with `feat(...)` and `docs(...)` titles holds the branch and the delivery title for the new default.
- **After the change.** `devops roadmap implement --plan` lists 30 Ready items of low effort that are neither Staged nor Planned, among them `fix`, `refactor`, `docs`, `test` and `feat` titles of priority P2 and P3, and no item of medium or high effort. `devops roadmap stage --plan --limit 1` plans #2152, a Ready P1 refactor, on the branch `refactor/2152-the-egress-checks-read-legacy-numeric`. It names #2147, a Ready P1 bug, first in the left-out list, because its plan is on `main`: the order is priority, then issue number.

## Existing Tool Considered

No tool is needed. The change edits two default values and the text and tests that name them. It builds no code and deletes none.
