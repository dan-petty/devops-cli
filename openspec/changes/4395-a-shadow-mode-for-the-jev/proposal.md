# Proposal: a shadow mode for the Jev intake labels

## Why

The setting `roadmap.intake.jev` is a bool (#4298). The offline comparison (`devops roadmap eval jev`, 25 closed issues and 16 duplicate cases) shows that Jev ties the triage model on type (17 of 25), is behind on priority (10 against 15), Value (12 against 16) and Effort (15 against 17), and finds 0 of 3 true duplicates (triage finds 1). Jev must not decide yet. The owner wants live observations of Jev on real new issues, to find its best use in the Service workflow. A bool has no mode in which Jev answers and decides nothing. ADR 0019 rule 6 asks for shadow first. This change closes #4395.

## What Changes

- `roadmap.intake.jev` becomes `off`, `shadow` or `on` (type `JevMode`, shared with `roadmap.stage.jev_screen`; the default stays `off`). The bool goes away with no shim. `StageJevScreen` is renamed `JevMode`.
- Add `src/devops_cli/roadmap/intake/intake_jev_shadow.py`. `ShadowIntakeModel` keeps the triage model for the proposal, and after intake checks the reply it asks Jev the same questions (one request for each candidate, the existing builders of `intake_jev`). It builds a `ShadowObservation`: the time, and for each field the Jev answer, its probability and the triage answer.
- Add the protocol `ObservingModel` to `intake_model.py`. `IntakeDecision.shadow` carries the mark, and the placement writes it as the job record key `intake.jev_shadow` (`IntakeRecordKey`) in the same write as the Priority. A Jev error changes nothing, writes no mark and counts `jev_error`.
- Add the counter `devops_cli_roadmap_intake_jev_shadow_total` (labels `field` and `outcome`; 5 fields and 3 outcomes: 15 series for each pod). The existing counter `devops_cli_roadmap_intake_jev_fields_total` stays for mode `on`: it counts which model gave a field, and the new one counts whether two models agree, so they do not duplicate each other.
- Add `devops roadmap eval jev --from-shadow` (with `--repo`): it reads the marks and the current labels of the issues, makes no model request, and prints the agreement and the accuracy of Jev and of triage against the final labels, a table of probability bands for each field, and the duplicate flags against the issues closed as a duplicate.
- Update `docs/roadmap/intake.md`, `docs/TELEMETRY.md`, `docs/CONFIGURATION.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, and the example ConfigMap.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-jev`: The setting has three modes, shadow records the answers of Jev beside the triage model, and the report reads the records.

## Impact

- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/intake/` (`intake.py`, `intake_jev.py`, `intake_jev_shadow.py`, `intake_model.py`, `intake_requests.py`), `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/jev_shadow_report.py`, `src/devops_cli/commands/roadmap_eval_jev.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/`.
- Tests: `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`, `tests/roadmap/test_roadmap_jev_shadow_report.py`, `tests/commands/test_roadmap_eval_jev.py`.
- Cluster: the live ConfigMap has no `roadmap.intake` key, so nothing breaks. An image from before this change refuses `jev: shadow` (a bool field), so the image must roll before the ConfigMap line is added.
- Cost: about 0.0001 USD for each candidate in mode `shadow`. The text of a public issue goes to the hosted Jev, which the owner policy allows. Intake refuses a candidate that holds a secret before any model call.

## Feasibility

- The pilot 1 screen has the same three modes: `src/devops_cli/roadmap/stage/stage_jev_screen.py` (`ScreenMode`, `off|shadow|on`) and ADR 0019 rule 6 ("Shadow first. Fail open").
- The job record already holds per-issue marks that survive restarts and are public with the issue: `src/devops_cli/roadmap/stores/store.py` (`ImplementRecordKey`, `RetitleRecordKey`), written by `RoadmapStore.set_field(..., marks=...)`. The key set `_JOB_RECORD_KEYS` is the list of keys the decoder reads.
- `intake_jev.py` builds one request with all questions (`_questions`) and `JevIntakeModel.propose` already decodes the answers, so shadow reuses the builders and adds no second client.
- Command output: `uv run devops ci test tests/roadmap/intake/test_roadmap_intake_jev.py tests/roadmap/intake/test_roadmap_intake_jev_shadow.py` passes with the Jev edge fake (`tests/support/fakes/jev.py`).
- The live ConfigMap holds no `roadmap.intake` key: `kubectl -n devops get cm devops-cli-config -o jsonpath='{.data.devops-cli\.yaml}'` shows `roadmap:` with `mcp`, `stage` (`jev_screen: shadow`), `alternatives` and `implement` only.

## Existing Tool Considered

The pattern exists in the project: `roadmap.stage.jev_screen` and `roadmap/decision_step.py` (ADR 0019), and the job record. This change reuses both. The report reuses `RoadmapStore.issues()` and `item_of`. No new library is needed, and no home-grown parser: the mark is read with pydantic. The code that this change deletes is the bool setting and its `if not settings.roadmap.intake.jev` branch.
