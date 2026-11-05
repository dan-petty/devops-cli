# Tasks

## 1. P1 items pass the limit (behavior)

- [x] 1.1 Write the failing tests: at the limit, `select_stageable` takes a `P0-Critical` item and a `P1-High` item and leaves out `P2-Medium` and `P3-Low`; the reason names the two priorities; `explain_item` gives `yes` for a P1 item; the inbox line names the two priorities.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_inbox.py`
- [x] 1.2 Add `CONST_ROADMAP_PLANNED_LIMIT_PRIORITIES` and `planned_limit_priorities`, change `_queue_full`, the two messages and the description of the setting, and regenerate the documentation with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. The documents state the rule (other)

- [x] 2.1 Change `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/roadmap/inbox.md`, `k8s/README.md` and `k8s/devops/configmap.example.yaml`.
  Verification: `uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
