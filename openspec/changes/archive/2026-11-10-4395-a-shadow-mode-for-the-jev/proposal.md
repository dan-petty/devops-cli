# Proposal: a shadow mode for the Jev intake labels

## Why

The setting `roadmap.intake.jev` is a bool (#4298). The offline comparison (`devops roadmap eval jev`, 25 closed issues and 16 duplicate cases) shows that Jev ties the triage model on type (17 of 25), is behind on priority (10 against 15), Value (12 against 16) and Effort (15 against 17), and finds 0 of 3 true duplicates (triage finds 1). Jev must not decide yet. The owner wants live observations of Jev on real new issues, to find its best use in the Service workflow. A bool has no mode in which Jev answers and decides nothing. ADR 0019 rule 6 asks for shadow first. This change closes #4395.

## What Changes

- `roadmap.intake.jev` becomes `off`, `shadow` or `on` (type `JevMode`, shared with `roadmap.stage.jev_screen`; the default stays `off`). The bool goes away with no shim. `StageJevScreen` is renamed `JevMode`. The setting gets the variable `DEVOPS_CLI_ROADMAP_INTAKE_JEV`, as `roadmap.stage.jev_screen` has one, so `docs/ENV_VARS.md` names the three modes.
- Add `src/devops_cli/roadmap/intake/intake_jev_shadow.py`. `ShadowIntakeModel` keeps the triage model for the proposal, and after intake checks the reply it asks Jev the same questions (one request for each candidate, the existing builders of `intake_jev`). It builds a `ShadowObservation`: the time, and for each field the Jev answer, its probability and the triage answer.
- Add the protocol `ObservingModel` to `intake_model.py`. `IntakeDecision.shadow` carries the mark, and the placement writes it as the job record key `intake.jev_shadow` (`IntakeRecordKey`) in the same write as the Priority. A Jev error changes nothing, writes no mark and counts `jev_error`.
- Shadow counts in the existing counter `devops_cli_roadmap_intake_jev_fields_total`, with three new values of the label `outcome`: `agree`, `differ` and `jev_error`. Mode `on` keeps `jev` and `fallback`. The labels stay `field` and `outcome`: 5 fields and 5 outcomes, at most 25 series. Mode `shadow` writes at most 15 of them and mode `on` at most 10. No second instrument is added. `JevOutcome` holds the five values, and `count_field` is the one place that writes the counter.
- Add `devops roadmap eval jev --from-shadow` (with `--repo`): it reads the marks and the current labels of the issues, makes no model request, and prints the agreement and the accuracy of Jev and of triage against the final labels, a table of probability bands for each field, and the duplicate flags against the issues closed as a duplicate.
- Update `docs/roadmap/intake.md`, `docs/TELEMETRY.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, and the example ConfigMap.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-jev`: The setting has three modes, shadow records the answers of Jev beside the triage model, and the report reads the records.

## Impact

- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/intake/` (`intake.py`, `intake_jev.py`, `intake_jev_shadow.py`, `intake_model.py`, `intake_requests.py`), `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/jev_shadow_report.py`, `src/devops_cli/commands/roadmap_eval_jev.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/`.
- Tests: `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`, `tests/roadmap/test_roadmap_jev_shadow_report.py`, `tests/commands/test_roadmap_eval_jev.py`, `tests/security/test_config_declarations.py`.
- Cluster: the live ConfigMap has no `roadmap.intake` key, so nothing breaks. An image from before this change refuses `jev: shadow` (a bool field), so the image must roll before the ConfigMap line is added.
- Metrics: no series goes away. Mode `on` is not live, so the counter has no series in the cluster today.
- Cost: about 0.0001 USD for each candidate in mode `shadow`. The text of a public issue goes to the hosted Jev, which the owner policy allows. Intake refuses a candidate that holds a secret before any model call.

## ADR 0020 and the decision-point registry

ADR 0020 names `intake.proposal` as step 3 of its migration, "after the shadow pull request of #4395 merges". This change does not build the registry. A later pull request migrates intake onto the decision-point registry that #4397 builds (the framework and the first migration, `stage.verify_screen`). That pull request removes `roadmap.intake.jev` and the counter `devops_cli_roadmap_intake_jev_fields_total` in favour of `roadmap.decisions` and `devops_cli_decision_point_total`, and states the ConfigMap change and its order. Until then the shadow records stay in the job record of each issue, so the data of the first fit survives the migration. One intake counter, not two, is also less to remove then.

## Feasibility

- The pilot 1 screen has the same three modes: `src/devops_cli/roadmap/stage/stage_jev_screen.py` (`ScreenMode`, `off|shadow|on`) and ADR 0019 rule 6 ("Shadow first. Fail open").
- The job record already holds per-issue marks that survive restarts and are public with the issue: `src/devops_cli/roadmap/stores/store.py` (`ImplementRecordKey`, `RetitleRecordKey`), written by `RoadmapStore.set_field(..., marks=...)`. The key set `_JOB_RECORD_KEYS` is the list of keys the decoder reads.
- `RoadmapStore.issues()` returns every issue, open and closed, so the report can join the final labels and the state reason `duplicate`.
- `intake_jev.py` builds one request with all questions (`_questions`) and `JevIntakeModel.propose` already decodes the answers, so shadow reuses the builders and adds no second client.
- `plan_intake` calls `NewCandidate.refuse_secrets()` before it builds the run, so a candidate with a secret reaches no model in any mode.
- Command output: `uv run devops ci test tests/roadmap/intake/test_roadmap_intake_jev.py tests/roadmap/intake/test_roadmap_intake_jev_shadow.py` passes with the Jev edge fake (`tests/support/fakes/jev.py`).
- The live ConfigMap holds no `roadmap.intake` key: `kubectl -n devops get cm devops-cli-config -o jsonpath='{.data.devops-cli\.yaml}'` shows `roadmap:` with `mcp`, `stage` (`jev_screen: shadow`), `alternatives` and `implement` only.

## Existing Tool Considered

The pattern exists in the project: `roadmap.stage.jev_screen` and `roadmap/decision_step.py` (ADR 0019), and the job record. This change reuses both, and it reuses the counter of mode `on`. The report reuses `RoadmapStore.issues()` and `item_of`. No new library is needed, and no home-grown parser: the mark is read with pydantic. The code that this change deletes is the bool setting and its `if not settings.roadmap.intake.jev` branch. Cost of the build, from the refined issue: about 90,000 tokens to build, about 20,000 tokens a year to keep, about 30,000 tokens to fix, and about 3 days of elapsed work.
