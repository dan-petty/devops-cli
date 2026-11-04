# Tasks

## 1. The stage job keeps the limit (behavior)

- [x] 1.1 Write the failing tests: the setting has a default and a least value, `select_stageable` takes no item at the limit and gives the limit as the reason, takes items under it, lets an item of the highest priority and a named item pass, and counts open Planned items only; the command `devops roadmap stage --plan` lists the reason.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_stage_settings.py`
- [x] 1.2 Add `roadmap.stage.planned_limit`, `planned_count` and the rule in `_Judge`, and pass the limit from `plan_stage`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_stage_settings.py tests/security/test_config_declarations.py`

## 2. The explain command names the limit (behavior)

- [x] 2.1 Write the failing tests: `explain_item` gives the reason of the limit and takes the limit from the settings.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py`
- [x] 2.2 Pass `planned_limit` from `explain_item` to `read_stage_selection`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py`

## 3. The inbox states the limit (behavior)

- [x] 3.1 Write the failing tests: `read_inbox` lists the line at the limit and no line under it.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py`
- [x] 3.2 Add `InboxKind.QUEUE`, its line and its texts, and pass the setting from the command.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_inbox_command.py`

## 4. Documents (documents)

- [x] 4.1 Document the limit in `docs/roadmap/stage.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md` and the example ConfigMap, and regenerate the documentation with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`
