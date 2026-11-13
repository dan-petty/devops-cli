# Proposal

## Why

The decision point framework of ADR 0020 has four gaps (#5272). A point in shadow loads with no cuts file, so `Thresholds.load` raises and every decision becomes a fallback with the band `none`, which looks the same as a failed request. `decide` calls `asyncio.run`, which raises `RuntimeError` inside a running event loop, and that error escapes because it is no class of `FAILED`. A decision record holds no time and no failure class, so the p95 time of a point and its share of failed requests are unknown. `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` is 60 while ADR 0020 section 7, as #4792 and ADR 0023 amend it, allows 92 series, so the registry refuses the full catalogue. The review of the decision-model documents adds a fifth gap, which the owner approved on 2026-11-12: the record names the configured model, not the dated snapshot that answered, and the chain uses a cuts file whose `model` is not the model in use.

## What Changes

- `check_modes` refuses the mode `shadow` and the mode `on` for a point whose cuts file is not in the repository, and the message names the point and the path.
- The description of `roadmap.decisions` states that a point in `shadow` or `on` needs a cuts file, and `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` hold the new text from the generator.
- `decide_all` sends the decision requests on the blocking portal of `src/devops_cli/ai/jev.py` and no longer calls `asyncio.run`; `adecide_all` awaits the same requests for a caller in an event loop.
- `ResolverChain` gives `adecide`, catches every error of the chain, returns the fallback and writes no error to the caller.
- `INSTRUMENTS` holds the histogram `devops_cli_decision_point_duration_seconds` and the counter `devops_cli_decision_point_failed_total`, with their per-point bounds, and `docs/TELEMETRY.md` lists both.
- Each decision adds one duration sample with the labels `point` and `resolver`, and each failed request adds one count with the class of its error.
- The decision record holds the dated model name that the decision model answered with, and the configured name only when the answer names none.
- The chain loads the cuts of a point before the request. When the `model` of the cuts file differs from the model target of `ai.decision_model`, the chain gives the fallback with the band `none`, sends no request and counts the class `model_mismatch`.
- The registry refuses a catalogue above the bound of 92 series, and every test of the bound reads `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` rather than a literal.
- The reason of the entry `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` in `LIMITS` of `tests/roadmap/test_roadmap_limit_classes.py` names the three parts of the bound of ADR 0020 section 7.
- ADR 0020 gains one dated line at the end of its `Status History` section that names the two instruments and their place in `docs/TELEMETRY.md` and the spec; no word of its body changes, so its `body-hash` stays.
- The change carries a spec delta for `decision-workflows`, `decision-steps` and `metric-instruments`, because the settings check, the resolver chain, the two functions of `decision_step.py`, the record and two instruments are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `decision-workflows`: An async caller awaits the decision, Each decision adds its duration, Each failed request counts by class, The record holds the dated model that answered, A cuts file of another model gives the fallback, The settings check the modes without the points, The registry bounds the series of its catalogue, A point fails back
- `decision-steps`: Decision requests use one event loop and a time limit
- `metric-instruments`: The decision point duration and failed instruments are declared and documented

## Impact

- Code: `src/devops_cli/roadmap/decision_table.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/ai/jev.py`, `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/config/constants.py`
- Documents: `docs/TELEMETRY.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`
- Tests: `tests/roadmap/test_roadmap_decision_table.py`, `tests/config/test_decision_point_settings.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_decision_step.py`, `tests/roadmap/test_roadmap_decision_point.py`, `tests/support/fakes/jev.py`, `tests/roadmap/test_roadmap_limit_classes.py`

## Weakened checks

- **`tests/roadmap/test_roadmap_decision_table.py::test_on_is_refused_for_a_point_with_no_cuts_file_and_shadow_is_not`**: Stopped: a change that lets a point with no cuts file take the mode `on`, and a change that refuses the mode `shadow` for that point. Safeguard: The mode `shadow` now also needs a cuts file, so task 1.1 replaces the test with `test_shadow_and_on_are_refused_for_a_point_with_no_cuts_file`. It asserts that each of the modes `shadow` and `on` raises a `ValueError` that names the point and the path of the cuts file.
- **`tests/roadmap/test_roadmap_decision_point.py::test_the_registry_refuses_a_catalogue_above_60_series`**: Stopped: a registry that accepts a catalogue above its series bound: eight points of 8 series give 64 label sets, above the bound of 60. Safeguard: ADR 0020 section 7 allows 92 series, so task 10.1 replaces the test with `test_the_registry_accepts_a_catalogue_at_the_bound_and_refuses_one_above_it`. It reads `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`, asserts that a catalogue of 92 label sets (eight points of 8 series and two of 14) loads, and asserts that a catalogue of 94 label sets (ten points of 8 series and one of 14) raises.

## Feasibility

- The probes confirm that the cited file exists: The path `src/devops_cli/roadmap/decision_table.py` is a file of the staging commit.
- The probes name two symbols, and a symbol is no path: The path `ResolverChain.decide` is no file of the staging commit. No commit in the history deleted or renamed it.
- The probes say `Thresholds` defines no field `load` in `src/devops_cli/roadmap/decision_step.py`; `load` is a classmethod, not a field: `src/devops_cli/roadmap/decision_step.py:106:@classmethod` and `src/devops_cli/roadmap/decision_step.py:107:def load(cls, path: Path) -> Self:`.
- The path `asyncio.run` is no file of the staging commit. No commit in the history deleted or renamed it.
- `read_file src/devops_cli/roadmap/decision_table.py` confirms gap 1: `src/devops_cli/roadmap/decision_table.py:44:if mode == "on" and not cuts[name].is_file():` refuses `on` only, so a point in `shadow` loads with no cuts file.
- `read_file src/devops_cli/roadmap/decision_step.py` confirms gap 2: `src/devops_cli/roadmap/decision_step.py:207:return asyncio.run(_decide_gathered(requests, model, model_name, settings, timeout))`.
- `RuntimeError` is no class of the fail-open tuple: `src/devops_cli/roadmap/decision_step.py:66:FAILED: Final[tuple[type[BaseException], ...]] = (`.
- The cuts load raises `FileNotFoundError` for a path that is not in the repository: `src/devops_cli/roadmap/decision_step.py:109:return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))`.
- The staged value that the plan changes: `src/devops_cli/config/constants.py:3884:CONST_ROADMAP_DECISION_POINT_MAX_SERIES: Final[int] = 60`; the change sets 92.
- `read_file src/devops_cli/roadmap/decision_point.py` gives the refusal of gap 4: `src/devops_cli/roadmap/decision_point.py:413:if count > CONST_ROADMAP_DECISION_POINT_MAX_SERIES:`.
- `file_symbols src/devops_cli/roadmap/decision_point.py` gives the chain: `src/devops_cli/roadmap/decision_point.py:242:def decide(self, given: T, *, subject: object) -> DecisionRecord:`.
- `read_file src/devops_cli/ai/jev.py` gives the portal that the plan reuses: `src/devops_cli/ai/jev.py:182:_portal = _portal_stack.enter_context(start_blocking_portal())`.
- `src/devops_cli/ai/jev.py:219:return _jev_portal().call(decision_model.decide, request, effective_settings)` is the one call of the portal, and the rename updates it.
- `references _jev_portal` gives files 3, lines 6: `src/devops_cli/ai/jev.py` (group 4), `tests/conftest.py:83` (decision 3), and one archived design under `openspec/changes/archive/`, which stays as it is.
- `read_file src/devops_cli/telemetry/instruments.py` gives the counter of the point: `src/devops_cli/telemetry/instruments.py:374:DECISION_POINT_TOTAL = Instrument(`.
- The duration histogram writes at most 3 series, one for each resolver: `src/devops_cli/roadmap/decision_point.py:125:*((Resolver.RULE,) if self.rule else ()),` and `src/devops_cli/roadmap/decision_point.py:126:*((Resolver.MODEL,) if self.asks_model else ()),` with `src/devops_cli/roadmap/decision_point.py:140:answered | {(self.name, Resolver.FALLBACK.value, NO_BAND, mode) for mode in modes}`.
- The two modes are from `src/devops_cli/roadmap/decision_point.py:132:modes = (Mode.SHADOW.value, Mode.ON.value)`.
- The failed counter holds the seven classes of the issue's proposed fix: "with a fixed set: `timeout`, `model_error`, `parse`, `secret`, `no_cuts`, `model_mismatch`, `other`". The verify of group 6 runs a census test that stops when the count is not seven. Each member is allowlisted: `timeout` for `TimeoutError`, `model_error` for `ModelAPIError`, `parse` for `UnexpectedModelBehavior` and `DecisionStepError`, `secret` for the new `SecretInDigestError`, `no_cuts` for `FileNotFoundError`, `model_mismatch` for the new `CutsModelMismatchError` of group 8, and `other` for every error that no class names.
- `read_file tests/roadmap/test_roadmap_decision_point.py` gives the tests that hold the number: `tests/roadmap/test_roadmap_decision_point.py:346:assert REGISTRY.series_count <= CONST_ROADMAP_DECISION_POINT_MAX_SERIES == 60` and `tests/roadmap/test_roadmap_decision_point.py:345:assert "60 series" in DECISION_POINT_TOTAL.description`.
- `read_file tests/roadmap/test_roadmap_decision_table.py` gives the test that accepts shadow with no file: `tests/roadmap/test_roadmap_decision_table.py:31:check_modes({"stage.unfitted": "shadow"}, cuts)`, which group 1 rewrites.
- `read_file src/devops_cli/config/settings.py` gives the field whose description changes: `src/devops_cli/config/settings.py:1667:decisions: Annotated[dict[str, DecisionMode], Variable()] = Field(`.
- `search_code DEVOPS_CLI_ROADMAP_DECISIONS` shows the same description in two generated documents, and `read_file` confirms both lines: `docs/CONFIGURATION.md:303:records its band and the real result` and `docs/ENV_VARS.md:119:records its band and the real result`, so group 12 regenerates both.
- `docs/ENV_VARS.md` is generated from the field declarations like `docs/CONFIGURATION.md`: `CONTRIBUTING.md:204:`devops config show`, `devops config env` and `docs/ENV_VARS.md` are generated from the declarations.` and `docs/adr/0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md:18:- **52 generated files are in git.** The docs inventory (`CONST_DOCS_INVENTORY`, class `generated`) lists them: 7 reference pages (`docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, ...`; the docs row of the gate refuses a generated document that differs from its source.
- `read_spec decision-workflows` gives the three requirements that the change modifies, `read_spec decision-steps` gives `Decision requests use one event loop and a time limit`, and `read_spec metric-instruments` holds no requirement for the two new instruments.
- The old verify never read `docs/adr`, so group 13 verifies with `uv run devops ci test tests/invariants/test_adr_records.py`: `tests/invariants/test_adr_records.py:19:assert record_problems(read_record_texts(ADR_DIRECTORY)) == []`.
- An accepted body does not change: `docs/adr/README.md:50:An agent never edits the body of an accepted record.` `docs/adr/README.md` also states that the body leaves out the `Status History` section, so group 13 adds one dated line, changes no body word, and `body-hash` stays; `src/devops_cli/docs/adr_records.py:186:yield f"{name}: the front matter has no body-hash: the hash of the body is {found}."` prints the hash if a hash were needed.
- The refine block's dated-model requirement is buildable: `tests/ai/test_jev_one_model_many_requests.py:114:assert (first.model_name, second.model_name) == ("typesafe/jev-1.14-20261014",) * 2` shows `DecisionResponse.model_name`, and the reply sets it at `tests/ai/test_jev_one_model_many_requests.py:38:"model": "typesafe/jev-1.14-20261014",`.
- The fake returns the configured name today: `tests/support/fakes/jev.py:145:return 200, {"model": CONST_AI_JEV_MODEL, "answers": answers, "usage": usage}`, so group 7 makes the answered name settable.
- The timeout class is testable with the fake: `tests/support/fakes/jev.py:84:def hold(self) -> None:` keeps a request open, and a point timeout of 0.01 seconds ends it in `TimeoutError`.
- The cuts-model check is buildable: the cuts file holds its model (`src/devops_cli/roadmap/decision_step.py:100:model: str` and `src/devops_cli/roadmap/stage/jev_screen_cuts.json:3:"model": "typesafe/jev-1.14",`), and the chain gets `ai.decision_model` as its model name (`src/devops_cli/roadmap/decision_point.py:326:model_name = settings.ai.decision_model if point.asks_model else ""`). The live ConfigMap sets `ai.decision_model: typesafe/jev-1.14`, so the check gives no fallback to the live screen.
- `check_modes` needs a checkout of the repository for its default `POINT_CUTS` table, and `Thresholds.load` needs a checkout of the repository for the cuts file of a point.
- `jev_portal` and `decide_with_jev` need a client of the Jev service when no `model` is given; the tests give `JevFake` and reach no network.
- `decide_all`, `adecide_all`, `ResolverChain.decide` and `ResolverChain.adecide` need a client of the Jev service when no `model` is given; the tests give `JevFake` and no network.
- `read_record_texts` and `record_problems` need a checkout of the repository for the records of `docs/adr`, and `emit` needs no client, no checkout and no network.
- The first checks of the branch are `uv run devops ci test tests/roadmap/test_roadmap_decision_table.py`, `uv run devops ci test tests/roadmap/test_roadmap_decision_step.py`, `uv run devops ci test tests/roadmap/test_roadmap_decision_point.py`, `uv run devops ci test tests/invariants/test_adr_records.py`, `uv run devops ci docs` and `uv run devops ci fail-to-pass --base origin/main`.
- Every verify command is `uv run devops ci test`, `uv run devops ci docs` or `uv run devops ci fail-to-pass`: `uv`, `python` and `pytest` are runner tools of the image, and no excluded tool is needed, so no row is NOT_IN_RUNNER. The fail-to-pass check needs a network and a checkout of `origin/main`.
- A verify that fails is the failure class `test` with the action repair, a row over its time limit is `timeout` with the action retry, and an infrastructure cut is `ci_infra` with the action retry. The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and no cluster token; the tests write only under the pytest `tmp_path` and need no network and no cluster.
- The issue's proposed fix and its acceptance criterion 1 name the fifth gap: "A cuts file of model A with `ai.decision_model` set to model B gives the fallback, and the failed counter holds `model_mismatch`." Group 8 delivers that criterion, and group 7 delivers the dated name of the record.

## Existing Tool Considered

anyio's `BlockingPortal`, which `src/devops_cli/ai/jev.py` already uses and which is already a dependency, carries the decision request, and the project's `Instrument` registry in `src/devops_cli/telemetry/instruments.py` carries the two new metrics. No new tool and no new dependency.

## Dependencies

- No open pull request changes a file of this change.
- Open issue #5239 plans one decision-model record that supersedes ADR 0019 and ADR 0020. If it merges first, group 13 adds its `Status History` line to the record that supersedes ADR 0020, and the shadow rule of group 1 must agree with that record.
- The metric `devops_cli_decision_point_total` is named by other files too: `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `docs/roadmap/stage.md`, the ADR 0020 record, `openspec/specs/decision-steps/spec.md`, `openspec/specs/decision-workflows/spec.md`, `openspec/specs/roadmap-stage/verification/spec.md`, `tests/roadmap/stage/test_roadmap_stage_jev_screen.py`, `tests/roadmap/test_roadmap_decision_point.py`, `tests/roadmap/test_roadmap_limit_classes.py` and the archived changes; this change edits the registry, the constant comment, the instrument description, the telemetry row, the ADR and the two bound tests, and leaves the rest unchanged.
