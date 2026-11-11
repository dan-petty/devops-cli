# Proposal: #4796

## Why

The model lane of each repository runs its rows one at a time. Before this change the order was `refine`, `retitle`, `stage`, `alternatives` (#4796). Since #4426, refine takes 7 items and is due every 17 minutes. A round of 7 refine items takes 35 to 65 minutes, so refine is due again when its round ends. The first round of each new Service pod ran refine first, and the pod restarts about every 1 to 1.5 hours. Stage often got no turn before the next restart.

On 2026-11-11, stage row time fell to 311 minutes from 688 minutes on 2026-11-10, while refine row time rose to 611 from 205 minutes. A new pod ran refine directly after a refine round 4 times, and no stage attempt ran from 17:36 to 18:54 UTC. 149 Ready items wait and 0 items are Planned, so stage, not refine, limits the plan pull requests.

## What Changes

- The model lane runs `retitle`, `stage`, `refine`, `alternatives`, in that order. Stage runs before refine, so the first round of a new pod stages first. Retitle stays just before stage, so stage reads the new titles. Alternatives stays after refine.
- A round in which refine set an item Ready writes the timestamp `stage_due` to `schedule.json`. Stage is due when that stamp is at or after its last success, so stage takes a new Ready item in the next round (#2659). This replaces the cross-job rule of the stage row, which read the outcome of refine in the same round.
- Refine keeps its limit (7) and interval (17 minutes). It takes the lane time that stage leaves. With no Ready item, a stage round only selects and calls no model.
- The order of the rows is the behavior of the Service that a person sees in `devops roadmap run --dry-run` and in the logs, so the change carries a spec delta for `roadmap-stage` and `roadmap-retitle`.

The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the stage row comes before refine and is due by the `stage_due` stamp.
- `roadmap-retitle`: the retitle row comes just before stage.

## Impact

- `src/devops_cli/roadmap/run.py`: the order of `MODEL_LANE_ROWS`, the `stage_due` stamp and its due check. `_stage_cross_job` is deleted.
- `src/devops_cli/config/constants.py`: `CONST_ROADMAP_STAGE_DUE_STAMP`.
- `k8s/README.md`, `docs/roadmap/intake.md`: the row order.
- No setting, ConfigMap key or metric changes. The next release of the Service image applies the change.

Expected effect, from a model of the lane with the measured numbers (refine 6.2 minutes for each item, a stage round of 32 to 49 minutes, a restart about every 80 minutes): stage rounds go from 0.62 to 0.70 an hour to 1.07 to 1.15 an hour. Refine items go from 5.7 to 6.6 an hour to 3.2 to 4.4 an hour, at or above the rate before #4426 (about 3 an hour). With no restart, both orders give the same result.

## Feasibility

- `src/devops_cli/roadmap/run.py` on origin/main: `_execute_due_rows` runs the due rows of the lane in the order of `MODEL_LANE_ROWS`, one at a time, and `_Poll.is_due` already reads the stamp `refine_due` that intake writes to `schedule.json`.
- Service logs of 2026-11-11 (devops-cli 0.112.2): `Refine round ... started: 7 item(s) taken` at 17:37:07, `ended` at 18:54:33, the first stage gate line at 19:17:53, then refine started again at 19:30:45 and 19:37:17 on two new pods.
- Prometheus `devops_cli_roadmap_row_seconds`: stage row time 688 minutes (2026-11-10) and 311 minutes (2026-11-11); refine 205 and 611 minutes.
- `src/devops_cli/roadmap/refine/refine.py` `plan_refine`: refine writes each item when it is done (#3631), so a stop costs refine at most the item in progress.

## Existing Tool Considered

The model lane is the scheduler of the Service; no open tool runs its rows. #4559 moves stage into its own Kubernetes Job, which is the long fix. This change only reorders the rows of the existing table, about 30 lines. Cost to build: about 150,000 tokens and 2 hours. Internal code that the change deletes: `_stage_cross_job` and the cross-job predicate of the stage row.
