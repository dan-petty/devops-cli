# Proposal: #4802

## Why

Three strict caps turn each refusal of the stage job into a loss (#4802). A reply that the checks refuse goes back to the planner one time only. A refused plan (`plan_defect`) waits 6 hours, and the ledger uses the same wait for a suspended row. A row that fails 3 rounds in a row is suspended, and one failed item fails the whole stage round. In the 7 days to 2026-11-11, the return cap ended 66 of about 110 failed stage rounds, and in 8 of 10 sampled items the returned reply had fewer problems. The stage row was suspended 25 times. Stage success was about 20%. The owner allowed the loosening of the roadmap caps on 2026-11-11, and asked for 80% success for each job before the caps get tuned. Only a code change can change these values now.

## What Changes

- The setting `roadmap.stage.gate_returns` (default 3) replaces `CONST_ROADMAP_STAGE_GATE_RETURNS` (1). Each check that refuses a reply sends it back this many times: the paths, title, plan body, create overlap, model module, OpenSpec validation and placeholder rules.
- `RETRY_AFTER` gives `plan_defect` 1 hour, not 6. The item wait, the explain reason and the retry time of a suspended stage row follow.
- The setting `service.max_failed_rounds` (default 6) replaces the fixed 3 rounds of the ledger of failed rounds.
- The docs and the specs name the new values and settings.

## Capabilities

- `roadmap-stage`: the returns of a refused reply come from `roadmap.stage.gate_returns`, and a refused plan waits 1 hour.
- `roadmap-failure-taxonomy`: `plan_defect` waits 1 hour.
- `roadmap-explain`: the reason of a held refused plan names the time 1 hour after the failure.
- `roadmap-service-limits`: the ledger reads `service.max_failed_rounds`.
- `roadmap-service-logs` and `roadmap-service-counters`: the scenarios follow the new limits.

## Impact

- A refused reply that makes progress gets up to 4 tries for each ask. The worst case of one item goes from 3 to 5 planner calls without a verifier, and from 7 to 13 with one. A return sends the refused reply and its problem, so it costs less than a new attempt from the first ask.
- A refused item skips one stage round (37 minutes) and not about 9. The return to New after `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT` refused plans on one body still limits its attempts.
- The stage row runs about 3.7 hours of failed rounds before a suspension, not about 1.9 hours. The other rows also get 6 rounds. The hourly GitHub request budget still limits the requests of a failing row.
- The owner can tune the returns and the row limit live in the ConfigMap. The change fits one pull request.

## Feasibility

- `src/devops_cli/roadmap/stage/stage.py` `_returned` reads the return count in one place, and `_settle` sends every refusal of the checks (problems, title, plan body, OpenSpec validation) through it. A schema break goes through the retries of pydantic-ai and does not change.
- `src/devops_cli/roadmap/run.py` `FailureLedger` takes its limit at construction; `service_jobs` builds the one ledger of the Service. `run.py` already reads `load_settings()`.
- `RETRY_AFTER` in `src/devops_cli/roadmap/failure.py` is the one table of the waits; stage, refine, intake and the ledger read it through `retry_after`.
- Measured with Loki and Prometheus of the Service and the refused-reply files, 2026-11-11: 66 of about 110 failed stage rounds name "also after a second try"; 25 stage suspensions in 7 days (16 with `plan_defect`); 8 of 10 sampled refused items shrank their problem text at the second reply (#4028 1595 to 149 characters, #4043 1390 to 305).
- Nested limits: each planner call keeps its tool call limit (200) and request limit (250). The stage row has no wall-clock deadline in the Service, and the 600 second stop drain still ends a round at its next GitHub request. The item wait (1 hour) is longer than the stage interval (37 minutes), and the row retry time (1 hour) is shorter than the 3 hour `for` of `RoadmapServiceRowSuspended`.

## Existing Tool Considered

No open tool holds the caps of the roadmap jobs of this project. The change uses the existing settings model (pydantic-settings, `Variable` markers) and the ConfigMap. Cost to build: about 60,000 tokens and 1.5 hours. The change deletes `CONST_ROADMAP_STAGE_GATE_RETURNS`.
