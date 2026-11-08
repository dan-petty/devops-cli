# Proposal

## Why

The request of the stage planner (#4046) is an untyped `dict[str, Any]`, built by `_Planner._request` in `src/devops_cli/roadmap/stage/stage.py`. The inputs that the gates need are not in it. They are instance fields of `_Planner`: `_probe_lines`, `_overlaps` and the creators that `_creators()` reads with a live call. So a gate cannot run again without the `_Planner` object and the open requests behind it. This blocks any later work that keeps a plan and judges it again (#4064). A dict also has no check of its keys: a typo in a key reaches the model with no error.

## What Changes

- Add the module `src/devops_cli/roadmap/stage/stage_request.py` with the pydantic model `StageRequest` (`extra="forbid"`). It holds the fields that the model reads (`number`, `title`, `body`, `context`, `capabilities`, `budget`, `rejected_plan`, `overlaps`, `metric_senders`, `probes`) and four fields that only the gates read (`issue_body`, `probe_lines`, `overlap_pulls`, `creators`). `GATE_ONLY_FIELDS` names the four.
- `StageRequest.for_model()` returns `model_dump(exclude=GATE_ONLY_FIELDS, exclude_none=True)`. The four optional keys are absent when they are empty, in the order of today, so the JSON that the model reads is the same as before.
- `gate_arguments(request, tree, ...)` builds the arguments of `check_proposal` from a `StageRequest` and the tree. The inputs that are not part of the request (`known`, `requirements`, `requirement_texts`, `read_text`, `registry`, `constants`, `search_evidence`) are keyword arguments.
- `_Planner._request` returns a `StageRequest`. `_gated`, `_verified` and `_repaired` send `request.for_model()` with `previous` and `problem`. `_problems` calls `gate_arguments` and reads no planner field for the gates.
- The model field `overlaps` (entry dictionaries) and the gate input of the same name (`Overlap` objects) clash. The gate input is `overlap_pulls`. The model field `probes` (text) and the gate input (lines) clash in the same way. The gate input is `probe_lines`. The gate also reads the whole issue body, and the model reads a body cut to the token limit, so `issue_body` is a gate-only field.
- `_request` reads the creators once, before the model call, where `_problems` read them after it. The reader is cached for the run and the gate always calls it, so the creators are equal. Only the order of the read changes. An item that a dependency blocks already reads them before the model call.
- The change alters no behavior that a consumer observes, so it has no spec delta and sets `skip_specs: true`. It stores nothing, adds no setting, and removes, renames or tightens no key of `k8s/devops/configmap.example.yaml`, no key of the live ConfigMap and no field of `Settings`. So it needs no test that loads the example ConfigMap into `Settings`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_request.py` (new), `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_request.py` (new)
- Documents: `docs/roadmap/package-layout.md`
- Deleted: the untyped `request` dictionary of `_Planner._request`, and the planner fields `_probe_lines`, `_overlaps` and `_metric_senders` after their values move into the request.

## Feasibility

- I read `src/devops_cli/roadmap/stage/stage.py`, `stage_change.py` and `stage_overlap.py` at `origin/main` 4f3c45cd and confirmed each claim of the issue. `_Planner._request` (stage.py line 1010) returns `dict[str, Any]` with the keys `number`, `title`, `body`, `context`, `capabilities` and `budget`, and adds `rejected_plan`, `overlaps`, `metric_senders` and `probes` only when they are set. `grep -n 'request: dict\[str, Any\]' src/devops_cli/roadmap/stage/stage.py` matches line 1025, so criterion 4 fails on the unchanged code.
- `_Planner._problems` is the one call of `check_proposal`. It reads `_probe_lines`, `_overlaps`, `_creators()` and `target.item.body`. `_creators()` calls the `open_creates` callable, which `cache()` wraps in `plan_stage`, so the run reads the store once.
- `Overlap` is a frozen dataclass in `stage_overlap.py`, and pydantic validates a standard dataclass as a field type, so `StageRequest` needs no new type.
- The planner path is pinned before the change. The tests `test_model_json_unchanged_through_the_planner` and `test_model_json_unchanged_on_the_return_of_a_refused_reply` pass on the unchanged code when the import of the new module is removed from the test module, so they describe today's JSON. The other tests of the module fail on the unchanged code because `devops_cli.roadmap.stage.stage_request` does not exist.
- No merged change and no open pull request does this work. #4040 and #4034 are merged and are the base. #3477 (request size) is closed. #4064 (keep the plan as a file) is open and needs this model. No ADR supersedes it.
- The set of gate inputs is the set of arguments of `check_proposal` that depend on the item, counted from its signature: `issue_body`, `probes`, `overlaps` and `plan_creates`. The other arguments depend on the commit or on the proposal, and stay keyword inputs of `gate_arguments`.

## Existing Tool Considered

pydantic, which the project already uses for every model: it gives the `extra="forbid"` check, `model_dump` with `exclude`, and JSON round trip, so no hand-made validation is built. No new library. The change deletes the untyped dictionary and three planner fields, and adds one small module.

## Dependencies

None. #4040 and #4034 are merged.
