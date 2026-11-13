# Design

## Decisions

- **Refuse the mode `shadow` at settings load, in `check_modes`, and not when a decision runs.**: A cuts file that is absent is a configuration error, so the load names the point and the path and no run turns every decision into a fallback.
- **Reuse the one process portal of `src/devops_cli/ai/jev.py` and rename `_jev_portal` to `jev_portal`, so `decision_step.py` imports a public name.**: A model binds its lock and its pooled client to the loop of its first request (#4319), so one loop serves the intake requests and the decision requests of a process.
- **Leave `tests/conftest.py` unchanged, although `references _jev_portal` lists it.**: `tests/conftest.py:83` names `reset_jev_portal`, which the change does not rename; only the private `_jev_portal` becomes public.
- **Catch `Exception` in `ResolverChain.decide` and in `adecide`, and classify an error that no class names as `other`.**: The docstring promises that no error of the model escapes; adding `RuntimeError` to `FAILED` leaves the next unlisted error to escape.
- **Give the failed counter the six classes `timeout`, `model_error`, `parse`, `secret`, `no_cuts` and `other`.**: The label set is fixed in code, so a point writes at most 6 failed series, and `other` holds every error that no class names.
- **Bound a point at 3 duration series and 6 failed series, and state both bounds in the description of the instrument.**: The `Resolver` enum has 3 members and the class set has 6, so the label sets of a point cannot grow without a change of code.
- **Keep the registry bound on the label sets of `devops_cli_decision_point_total` and set `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` to 92.**: ADR 0020 section 7 allows 60 series for the first catalogue, 24 for the three `brain.*` points and 8 for `resolve.question_class`.
- **Make each test of the bound read `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` and build 92 series and 94 series.**: A point writes 8 or 14 label sets, so no sum of points gives exactly 93, and a test that holds the number goes stale with the constant.
- **Rewrite the reason of the limits table entry for the series bound in the same change that raises the bound, and name that path in the task that rewrites it.**: The table declares that path for every constant of the `CONST_ROADMAP_` prefix, and its reason states the old bound, so a stale reason contradicts the new value.
- **Record the dated model name of the response in the decision record, and keep the configured name only when the response names none.**: The refine block requires `response.model_name`, and `DecisionResponse.model_name` holds the dated snapshot that answered, so the record shows which snapshot served a request.
- **Add one dated line to the `Status History` section of ADR 0020 and change no word of its body.**: `docs/adr/README.md` forbids an edit of the body of an accepted record, and the body hash covers the body without the `Status History` section, so the line records the instruments and the hash stays.
- **Regenerate `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` from the description of the field `roadmap.decisions` instead of editing the rows by hand.**: Both documents hold that description and both are generated from the field declarations, so `uv run devops ci docs` refuses either one that differs from its source.
- **Keep the two new metrics separate from `devops_cli_decision_point_total`.**: A duration is a histogram and a failure class is a second counter, and the registry bound counts the label sets of the decision counter alone.
- **Keep the cuts-model mismatch class out of this change.**: The issue's proposed fix names the fixed set of six classes and the live screen runs in shadow with a cuts file of the configured model, so a seventh class and a new fallback path need their own item.

## Rejected alternatives

- **Add `RuntimeError` to the tuple `FAILED` of `decision_step.py`.**: `src/devops_cli/roadmap/decision_step.py:66:FAILED: Final[tuple[type[BaseException], ...]] = (` lists seven classes, and the next error that no class names escapes the chain again.
- **Keep `asyncio.run` and start a second thread with `asyncio.new_event_loop` for a caller that runs an event loop.**: `src/devops_cli/ai/jev.py:182:_portal = _portal_stack.enter_context(start_blocking_portal())` already keeps one loop open for the process, and a second loop closes the pooled client of a shared model (#4319).
- **Leave the mode `shadow` without a cuts file and count the missing file as a failure class.**: `src/devops_cli/roadmap/decision_table.py:44:if mode == "on" and not cuts[name].is_file():` refuses `on` only, so a shadow decision is a fallback that no query can tell from a failed request.
- **Set the bound to 93 or drop the registry bound.**: `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md:92:so the counter has at most **92 series**` is the bound of the ADR, and a bound of 93 admits a catalogue that the ADR refuses.
- **Edit section 7 of ADR 0020 in place to name the two instruments.**: `docs/adr/README.md:50:An agent never edits the body of an accepted record.` and the hash of the body would fail at `tests/invariants/test_adr_records.py`.
- **Keep the configured model name in the record and give the dated model no task.**: `tests/ai/test_jev_one_model_many_requests.py:114:assert (first.model_name, second.model_name) == ("typesafe/jev-1.14-20261014",) * 2` shows the field, and the refine block requires the record to hold it.
- **Add a seventh failure class `model_mismatch` for a cuts file of another model.**: The issue's proposed fix names the fixed set `timeout`, `model_error`, `parse`, `secret`, `no_cuts`, `other`, so a seventh class changes the contract that the issue states.
- **Regenerate only `docs/CONFIGURATION.md` and leave the `docs/ENV_VARS.md` row as it is.**: `docs/ENV_VARS.md:119:records its band and the real result` holds the same description, and `docs/adr/0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md:18:- **52 generated files are in git.** The docs inventory (`CONST_DOCS_INVENTORY`, class `generated`) lists them: 7 reference pages (`docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, ...` makes both generated, so a stale row fails the docs row of the gate.

## Unchanged references

- `tests/conftest.py` (import): It names `reset_jev_portal`, which the change does not rename; only the private `_jev_portal` becomes public.
