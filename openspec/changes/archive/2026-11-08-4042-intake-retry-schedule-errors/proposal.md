# Proposal

## Why

Two faults in the roadmap Service (#4042, part of #3027).

First, an Item that a person changes between the plan and the write of an intake round makes `set_field` raise `RoadmapItemChangedError`. It is a `GitHubOperationError`, so `apply_intake` records a failed placement and the round fails. The same error means "nothing was written" in the claim code. The candidate stays in the intake record and is decided again, so no data is lost, but the round counts as failed. A failed round also stops the `refine_due` stamp of a P0 item that the same round placed.

Second, `_read_schedule` reads a `schedule.json` that it cannot read as empty. Every row with `first_run_due` then becomes due at once, with model spend and no error.

## What Changes

- In `src/devops_cli/roadmap/intake/intake.py`, `apply_intake` catches `RoadmapItemChangedError` before `GitHubOperationError`. It logs one INFO line that names the candidate and adds no `PlacementFailure`. The candidate is not in `placed`, stays in the intake record and is decided again.
- `IntakeApplied` reports whether a critical fix or P0 decision was placed. `apply_intake` sets it only for a decision whose placement did not fail and was not refused as changed. This replaces `_places_critical_or_p0(plan)`, which reads the plan and not the result.
- In `src/devops_cli/roadmap/run.py`, `_run_intake_adapter` and `_intake_one` run the same block, so one helper writes the `refine_due` stamp before `raise_for_failed_placements`. The issue names only `_run_intake_adapter`; the webhook path `_intake_one` has the same fault and gets the same fix.
- `_read_schedule` raises `RoadmapRunError` for an unreadable file, a file that is not a JSON object, a value that is not a string and a bad timestamp. The text names the file and the remedy, in the style of `read_intake_record`. A missing file stays empty. The new text is `MESSAGES.roadmap.run_schedule_unreadable` in `src/devops_cli/lang/en/messages.py`.
- `k8s/README.md` (item 17) says that an unreadable `schedule.json` fails the round and names the file.
- The change alters what a consumer sees (a round result, a log line, an error), so it carries spec deltas: `roadmap-intake-failures` (ADDED) and the new capability `roadmap-schedule-record`.
- Behavior change on the live volume: a corrupt `schedule.json` now fails every round, with an ERROR log line that names the file, instead of running every row at once. The remedy is to repair or remove the file; a removed file reads as a first run. `server/service.py` already logs a round error at ERROR and counts `result=error`. No alert is added (#3666 counts a round that fails before its first row).
- Rollout rule (2026-11-07): this change removes, renames and tightens no setting. `k8s/devops/configmap.example.yaml` and the live ConfigMap stay as they are. `tests/config/test_k8s_devops_runtime.py::test_config_targets_the_in_cluster_gateway_and_holds_no_credential` already loads the example ConfigMap into `Settings`, so the change adds no second copy of that test.
- Not in this change: the failure count and class of a placement (#4061).
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-schedule-record`: What a round does with a `schedule.json` that it cannot read.

### Modified Capabilities

- `roadmap-intake-failures`: An Item changed between the plan and the write is no failure; the stamp of a P0 placement survives a failed placement.

## Impact

- Code: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `k8s/README.md`
- Tests: `tests/roadmap/intake/test_roadmap_intake_item_changed.py` (new), `tests/roadmap/test_roadmap_schedule_unreadable.py` (new), `tests/roadmap/intake/test_roadmap_intake_github_requests.py`

## Feasibility

I read these files at origin/main 08b42d61 and found the premise true: `src/devops_cli/roadmap/intake/intake.py` (`apply_intake` catches `GitHubOperationError` after the rate-limit errors, and `_failed_placement` makes the `PlacementFailure`), `src/devops_cli/roadmap/stores/store.py` (`require_unchanged` raises `RoadmapItemChangedError` from `set_field`), `src/devops_cli/exceptions/roadmap.py` (`RoadmapItemChangedError` subclasses `GitHubOperationError`), `src/devops_cli/roadmap/claim.py` (`service_claim` treats the same error as "nothing written") and `src/devops_cli/roadmap/run.py` (`_read_schedule` returns `{}` on `OSError`, `JSONDecodeError` and a non-object, and skips a non-string value and a bad timestamp; two identical blocks call `raise_for_failed_placements` before `_places_critical_or_p0`).

The new tests run the code at origin/main and fail there for these reasons: `RoadmapIntakeError` is raised for an Item that changed, the `INFO` line is a `WARNING` that counts a failure, the stamp is missing after a real placement failure, and `_read_schedule` does not raise. The run is `uv run devops ci fail-to-pass --base origin/main`. The existing tests `test_a_priority_a_person_sets_between_the_plan_and_its_write_stays` and `test_a_value_a_person_sets_between_the_plan_and_its_write_stays_and_the_next_run_finishes` asserted the old failure and now assert none; they fail on origin/main.

No merged pull request, open pull request or newer issue does this work. The only open pull request that touches intake is a plan-claim set count, which is other code. #4034 (#4080) is merged.

## Existing Tool Considered

No library covers this: the need is one extra `except` clause, one result field and one raise in code that exists. The change reuses `RoadmapRunError`, the style of `read_intake_record` and the catch in `claim.py`. It builds no new helper beyond one function that merges two identical blocks of `run.py`, and so it deletes `_places_critical_or_p0` and the second copy of the block. Cost to build: about 40k tokens and 2 hours; to keep: about 2k tokens a quarter; to fix: about 10k tokens and 0.5 hours.
