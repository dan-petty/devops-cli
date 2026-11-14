# Tasks

## 1. Refuse shadow for a point with no cuts file

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_table.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_decision_table.py`. Changes: `src/devops_cli/roadmap/decision_table.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_decision_table.py`.

- [x] 1.1 Rewrite `test_on_is_refused_for_a_point_with_no_cuts_file_and_shadow_is_not` in `tests/roadmap/test_roadmap_decision_table.py` as `test_shadow_and_on_are_refused_for_a_point_with_no_cuts_file`: it asserts that each of the two modes raises a `ValueError` that names the point and the path
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_table.py` fails on the base
- [x] 1.2 Refuse the mode `shadow` and the mode `on` in `check_modes` when `cuts[name].is_file()` is false, and say so in its docstring. Reword `decision_point_unfitted` so that it names both modes and says that `off` is the mode that runs with no cuts file
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_table.py` passes

## 2. Name the shadow rule in the setting description

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `tests/config/test_decision_point_settings.py`. Changes: `src/devops_cli/config/settings.py`, `tests/config/test_decision_point_settings.py`.

- [x] 2.1 Add `test_the_decisions_description_names_the_shadow_rule` to `tests/config/test_decision_point_settings.py`: it reads the description of the field `RoadmapConfig.decisions` and asserts that it names `shadow` and a cuts file in the repository
  - Verification: `$ uv run devops ci test tests/config/test_decision_point_settings.py` fails on the base
- [x] 2.2 Extend the `description` of the field `decisions` of `RoadmapConfig` so that it states that a point in `shadow` or in `on` needs a cuts file in the repository, and that the load stops when the file is absent
  - Verification: `$ uv run devops ci test tests/config/test_decision_point_settings.py` passes

## 3. Declare the duration histogram and the failed counter

Kind: behavior. Reads: `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 3.1 Add `test_the_decision_point_duration_and_failed_instruments_are_declared` to `tests/telemetry/test_telemetry_instruments.py`: it asserts that both metrics are in `INSTRUMENTS` with their kind and unit and that `docs/TELEMETRY.md` lists both
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [x] 3.2 Add `DECISION_POINT_DURATION`, a histogram of the unit `s` with the labels `point` and `resolver` and the bound of 3 series, and `DECISION_POINT_FAILED_TOTAL`, a counter of the unit `1` with the labels `point` and `error`, the seven classes and the bound of 7 series, to `src/devops_cli/telemetry/instruments.py` and to its export list
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes
- [x] 3.3 Edit `docs/TELEMETRY.md` to add a row for each of the two new instruments, with its kind, its unit, its labels and its series bound
  - Verification: `$ uv run devops ci docs` passes

## 4. Send the decision requests on the Jev portal

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/ai/jev.py`, `tests/roadmap/test_roadmap_decision_step.py`. Changes: `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/ai/jev.py`, `tests/roadmap/test_roadmap_decision_step.py`.

- [x] 4.1 Add `test_decide_all_and_adecide_all_answer_inside_a_running_event_loop` to `tests/roadmap/test_roadmap_decision_step.py`: it runs each of the two from a coroutine that `asyncio.run` drives, with the fake Jev endpoint, and asserts the responses in order
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_step.py` fails on the base
- [x] 4.2 Rename `_jev_portal` to `jev_portal` in `src/devops_cli/ai/jev.py`, add it to `__all__`, and update the one call in `decide_with_jev`. Replace the `asyncio.run` call of `decide_all` with `jev_portal().call(_decide_gathered, requests, model, model_name, settings, timeout)`, import `jev_portal` inside `decide_all` as `create_jev_model` is imported, and add `adecide_all`, which awaits `_decide_gathered`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_step.py` passes

## 5. Answer a chain decision inside a running event loop

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_step.py`, `tests/roadmap/test_roadmap_decision_point.py`. Changes: `src/devops_cli/roadmap/decision_point.py`, `tests/roadmap/test_roadmap_decision_point.py`.

- [x] 5.1 Add `test_decide_and_adecide_answer_inside_a_running_event_loop` to `tests/roadmap/test_roadmap_decision_point.py`: one coroutine calls `decide` and awaits `adecide` with the fake model, and asserts that each gives the model decision and the band of the cuts
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` fails on the base
- [x] 5.2 Split the band step of `_resolve` into a helper that both paths share, add `_aresolve`, which awaits `adecide_all`, and add `adecide`, which builds the record, logs it and counts it as `decide` does
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` passes

## 6. Give the fallback for every error and count its class

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/test_roadmap_decision_point.py`. Changes: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_step.py`, `tests/roadmap/test_roadmap_decision_point.py`.

- [x] 6.1 Add `test_a_failed_request_gives_the_fallback_and_counts_its_class` to `tests/roadmap/test_roadmap_decision_point.py`: with a model that raises `RuntimeError` it asserts the fallback, the band `none` and one count with `error` equal to `other`, and with a fake endpoint that holds the request and a point timeout of 0.01 seconds it asserts one count with `error` equal to `timeout`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` fails on the base
- [x] 6.2 Add the enum `FailureClass` with the seven values of the failed counter and the function `failure_class(error)` to `src/devops_cli/roadmap/decision_step.py`, and raise a new `SecretInDigestError`, a subclass of `DecisionStepError`, from `DecisionPoint.request`. Catch `Exception` in `decide` and in `adecide` of `ResolverChain`, log the cause and emit `DECISION_POINT_FAILED_TOTAL` with the point and the class. Add a census test that counts the members of `FailureClass` and fails when the count is not seven
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` passes

## 7. Record the dated model that answered

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_point.py`, `tests/support/fakes/jev.py`, `tests/roadmap/test_roadmap_decision_point.py`. Changes: `src/devops_cli/roadmap/decision_point.py`, `tests/support/fakes/jev.py`, `tests/roadmap/test_roadmap_decision_point.py`.

- [x] 7.1 Add `test_the_record_holds_the_dated_model_that_answered` to `tests/roadmap/test_roadmap_decision_point.py`: it sets the answered model of the fake to `typesafe/jev-1.14-20261014` and asserts that the record holds that name and not the configured one
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` fails on the base
- [x] 7.2 Add `answered` to `JevFake` and use it as the `model` field of its reply, so a test names the dated model. Carry the model name of the response in `_Resolved`, put it in the `model` field of `DecisionRecord`, and keep the configured name only when the response names none
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` passes

## 8. Give the fallback for a cuts file of another model

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_decision_point.py`. Changes: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_decision_point.py`.

- [x] 8.1 Add `test_cuts_of_another_model_give_the_fallback_and_count_model_mismatch` to `tests/roadmap/test_roadmap_decision_point.py`: it writes a cuts file of the model `typesafe/jev-1.13` and builds the chain with the model name `Settings(ai={"decision_model": "typesafe/jev-1.14"}).ai.decision_model`, as `chain_of` does, and asserts the fallback, the band `none`, no request to the fake and one count with `error` equal to `model_mismatch`. A second case builds the chain with the gateway route `litellm:typesafe/jev-1.14` over cuts of `typesafe/jev-1.14` and asserts the decision of the model and the band of the cuts
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` fails on the base
- [x] 8.2 Add `CutsModelMismatchError`, a subclass of `DecisionStepError`, to `src/devops_cli/roadmap/decision_step.py`, and make `failure_class` map it to `model_mismatch` before it maps `DecisionStepError` to `parse`. Add a helper that `_resolve` and `_aresolve` call after the rule step and before `decide_all` or `adecide_all`. It loads the cuts and raises `CutsModelMismatchError` when their `model` differs from the model target of the chain: the name after a provider prefix such as `litellm:`, or the whole name when it has no prefix. Add the message `decision_point_cuts_model`, which names the point, the model of the cuts and the model in use
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` passes

## 9. Add the duration of each decision

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/test_roadmap_decision_point.py`. Changes: `src/devops_cli/roadmap/decision_point.py`, `tests/roadmap/test_roadmap_decision_point.py`.

- [x] 9.1 Add `test_one_decision_adds_one_duration_sample` and `test_the_decision_instruments_add_at_most_three_and_seven_series_to_a_point` to `tests/roadmap/test_roadmap_decision_point.py`: the first decides one case and asserts one sample of the histogram with the point and the resolver `model`, and the second runs one point in both modes with the rule, the model and the fallback and counts the label sets of both instruments
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` fails on the base
- [x] 9.2 Time the resolution of each decision with `time.perf_counter` and emit `DECISION_POINT_DURATION` with the point and the resolver of the record, on the path of `decide` and of `adecide`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` passes

## 10. Raise the series bound to 92

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `tests/roadmap/test_roadmap_decision_point.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `tests/roadmap/test_roadmap_decision_point.py`.

- [x] 10.1 Rewrite `test_the_registry_refuses_a_catalogue_above_60_series` in `tests/roadmap/test_roadmap_decision_point.py` as `test_the_registry_accepts_a_catalogue_at_the_bound_and_refuses_one_above_it`: it builds 92 label sets from eight points of 8 series and two of 14, then 94 from ten of 8 and one of 14, and reads `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` for both
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` fails on the base
- [x] 10.2 Set `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` to 92 and state in its comment that ADR 0020 section 7 allows 60 + 24 + 8 series. State the bound of 92 series in the description of `DECISION_POINT_TOTAL`. Change `test_one_counter_counts_the_decisions_and_states_the_bound_of_the_catalogue` to read the constant instead of the number 60
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py` passes
- [x] 10.3 Edit the row of `devops_cli_decision_point_total` in `docs/TELEMETRY.md` to the bound of 92 series
  - Verification: `$ uv run devops ci docs` passes

## 11. Name the new bound in the table of roadmap limits

Kind: other. Reads: `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 11.1 Rewrite the reason of the entry `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` in `LIMITS` of `tests/roadmap/test_roadmap_limit_classes.py` to the three parts of the bound of ADR 0020 section 7: 60 series for the first catalogue, 24 for the three `brain.*` points and 8 for `resolve.question_class`. Keep the class `kept`, and keep `test_every_class_in_the_table_is_a_known_class_with_a_reason` passing
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` passes

## 12. Regenerate the configuration and variable documents

Kind: other. Reads: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `src/devops_cli/config/settings.py`. Changes: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 12.1 Regenerate the rows of `roadmap.decisions` in `docs/CONFIGURATION.md` and in `docs/ENV_VARS.md` from the description of the field, so that both state that a point in `shadow` or `on` needs a cuts file
  - Verification: `$ uv run devops ci docs` passes
- [x] 12.2 Edit `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` with the output of the docs generator
  - Verification: `$ uv run devops ci docs` passes

## 13. Record the instruments in the Status History of ADR 0020

Kind: other. Reads: `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`, `docs/adr/README.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`.

- [ ] 13.1 Add one dated line to the end of the `Status History` section of ADR 0020, in the `Living detail moved to <path> (#N).` form of `docs/adr/README.md`, and name `docs/TELEMETRY.md` and the spec of `decision-workflows` as the place of the two instruments and their bounds. Change no word of the body, so `body-hash` stays
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py` passes
- [ ] 13.2 Edit `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md` in its `Status History` section only
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 10: `uv run devops ci fail-to-pass --base origin/main` shows tests that fail on main and pass on the branch:
- Group 1: Settings with `shadow` for a point with no cuts file stop the load, and the error names the point and the path.
- Group 5: `decide`, called inside a running event loop with a fake decision model, gives a model decision.
- Group 6: With a model that raises `RuntimeError`, `decide` gives the fallback.
- Group 9: One decision adds one sample to the duration histogram.
- Group 6: A timeout adds one count with `error="timeout"`.
- Group 10: A registry of 92 series loads, and a registry of 94 series raises.
- Group 8: A cuts file of model A with `ai.decision_model` set to model B gives the fallback, and the failed counter holds `model_mismatch`.
- Group 7: A reply that names a dated model puts that dated name in the decision record.
- Group 10: No test holds the number 60 for the bound; each bound test reads the constant.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
