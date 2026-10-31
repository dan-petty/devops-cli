# Tasks

## 1. The stage default

- [x] Write failing tests. In `tests/roadmap/test_roadmap_stage_settings.py` the default filter is `["status=ready"]`. In `tests/k8s/test_k8s_configmap.py` the example ConfigMap holds the filter `["status=ready"]` and equals `DEFAULT_ROADMAP_STAGE_FILTER`. In `tests/roadmap/test_roadmap_stage_selection.py`, with `parse_filters(())`, a Ready P3 chore, a Ready P2 feature and a Ready P0 docs item are all named, the P0 item goes first, and the targets get the types `docs`, `feat` and `chore`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_stage_selection.py tests/k8s/test_k8s_configmap.py`
- [x] Set `DEFAULT_ROADMAP_STAGE_FILTER` to `("status=ready",)` in `src/devops_cli/config/defaults.py` and update its comment. Set the filter of `k8s/devops/configmap.example.yaml` to `status=ready`. Update the module text of `src/devops_cli/roadmap/stage.py` and the `stage` help text in `src/devops_cli/lang/en/help.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_stage_selection.py tests/k8s/test_k8s_configmap.py`

## 2. The implement default

- [x] Write failing tests in `tests/roadmap/test_roadmap_implement_selection.py`: `DEFAULT_IMPLEMENT_FILTERS` is `("status=ready", "effort=low")`. A staged low-effort feature and a staged low-effort P3 chore are selected. A medium-effort and a high-effort item are not named. A P0 item goes before a P3 item. A Planned `feat(...)` item gets a `feat/` branch.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_implement_planned.py`
- [x] Set `DEFAULT_IMPLEMENT_FILTERS` in `src/devops_cli/roadmap/implement.py` and update its comment and module text. Update the `implement` help text in `src/devops_cli/lang/en/help.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_implement_planned.py tests/roadmap/test_roadmap_implement_job.py`

## 3. The review findings

- [x] Write failing tests in `tests/roadmap/test_roadmap_stage_selection.py`: under the default filter an item with the label `type/epic`, an item with sub-issues and an item with both are left out with the tracker reason, and a plain bug is staged.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py`
- [x] Add `Item.sub_issues` in `src/devops_cli/roadmap/store.py`, the check `_tracker` in `src/devops_cli/roadmap/stage.py` and the text `stage_left_tracker` in `src/devops_cli/lang/en/messages.py`. State in the proposal that the per-round limit is the only bound on open drafts.
  - Verification: `uv run devops ci test tests/roadmap`

## 4. The documentation

- [ ] Regenerate the documents.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2906-wide-stage-and-implement-filters`
