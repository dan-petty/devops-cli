# decision-workflows Specification Delta

## ADDED Requirements

### Requirement: Guards run before rule and model in fixed order
A `DecisionPoint` MAY declare ordered `Guard` checks evaluated before rule and model in fixed order (`service_draining`, `hard_ceiling`, `outer_limits`, `loop_guard`). On the first failing guard, `ResolverChain` SHALL stop, send zero model requests, and return `Resolver.FALLBACK` with `band=None` and `guard` naming that guard.

#### Scenario: First failing guard short-circuits rule and model
- **WHEN** `service_draining` and `loop_guard` both fail on an input
- **THEN** `ResolverChain` stops at `service_draining`, records `resolver=Resolver.FALLBACK`, `band=None`, `guard="service_draining"`, and sends zero model requests

#### Scenario: Ceiling, outer limits, and loop guards short-circuit in order
- **WHEN** service is not draining, `hard_ceiling` passes, and `outer_limits` fails (or `loop_guard` fails with `4` identical call+answer repeats or `3` identical failing calls)
- **THEN** `ResolverChain` stops at that guard, records its name in `DecisionRecord.guard`, and sends zero model requests

### Requirement: Fit bar gates mode on
Before a fit-bar-gated point (such as `implement.extension`) can run in mode `on`, its cuts file SHALL satisfy the fit bar: at least `30` labelled outcomes, at least `10` cases per label, and a passing halves evaluation (`report` with passing halves metrics). No default constant cut SHALL substitute for fitted cuts. Both `check_modes` at settings load and `ResolverChain` at runtime SHALL refuse or block `on` activation without fitted cuts meeting the fit bar.

#### Scenario: Unfitted or undersized cuts fail the fit bar for mode on
- **WHEN** `check_modes` checks `{"implement.extension": "on"}` with a missing file, fewer than `30` cases, fewer than `10` per label, or a failed halves report
- **THEN** `check_modes` refuses the configuration with an error naming the point

#### Scenario: Fitted cuts meeting the fit bar pass
- **WHEN** a cuts file has at least `30` cases, at least `10` per label, and passing halves evaluation in `report`
- **THEN** `Thresholds.fit_bar_problems()` returns `[]`

### Requirement: Rule stands, rule mode collects answers, and model errors fall back to rule
`DecisionRecord` SHALL record `rule_band`, `model_band`, and `guard`. When a rule returns a non-None `Band`, it SHALL stand across `shadow`, `rule`, and `on`. In mode `rule`, `ResolverChain` SHALL need no cuts file, SHALL record any model answers with `model_band=None` within timeout, and SHALL fall back to the rule on model error or timeout, safely inside an active asyncio loop.

#### Scenario: Rule mode collects model answers with model_band None
- **WHEN** a point runs in `Mode.RULE` with no cuts file and a configured fake decision model
- **THEN** `DecisionRecord.answers` records the model probabilities, `DecisionRecord.model_band` is `None`, and the rule behavior determines whether the action occurs

#### Scenario: Timeout or model error falls back to the rule inside a running event loop
- **WHEN** `decide` or `adecide` runs inside `asyncio.run(...)` with a holding or failing fake model at `5.0 s` (or shorter test timeout)
- **THEN** it raises no `RuntimeError`, counts the failure under `devops_cli_decision_point_failed_total`, and returns the fallback/rule outcome cleanly

### Requirement: Implement extension is registered as a soft-cap decision point
The registry SHALL hold `implement.extension` (`IMPLEMENT_EXTENSION`), pairing closed `NoulQuestion` prompts, `5.0` s timeout, ordered guards, and the progress rule (`18` series: `7` in `shadow`, `7` in `on`, `4` in `rule`), and `POINT_CUTS` SHALL declare its unfitted cuts path so `Mode.RULE` runs without a cuts file while `shadow` and `on` wait until fitted cuts exist.

#### Scenario: implement.extension accepts rule and rejects unfitted shadow/on
- **WHEN** `check_modes` checks `implement.extension`
- **THEN** `"rule"` and `"off"` pass without a cuts file while `"shadow"` and `"on"` are refused until fitted cuts exist

## MODIFIED Requirements

### Requirement: The mode of each point is a setting
The setting `roadmap.decisions` SHALL map the name of a point to a mode: `off`, `shadow`, `rule` or `on`. A point that is not in the mapping SHALL be `off`. A key that is not the name of a registered point SHALL make the settings fail to load. The registry SHALL accept `off` and `rule` without a cuts file in the repository, SHALL refuse `shadow` and `on` when a point has no fitted cuts in the repository, and SHALL refuse `on` when a fit-bar-gated point fails the fit bar.

#### Scenario: A key that names no point
- **WHEN** the settings load with a key of `roadmap.decisions` that is not a registered point
- **THEN** the load fails and the error names the key and the registered points

#### Scenario: Rule without cuts succeeds
- **WHEN** the settings load with the mode `rule` for a point with no cuts file
- **THEN** settings load succeeds and leaves `rule` mode active

#### Scenario: On without cuts
- **WHEN** the settings load with the mode `on` for a point that has no fitted cuts
- **THEN** the load fails and the error names the point

### Requirement: The settings check the modes without the points
The settings SHALL check the keys and the modes of `roadmap.decisions` against a table of the name and the cuts file of each point, and SHALL NOT import `pydantic_ai` or a point module to do it. The table SHALL hold the same names and cuts files as the registry. The settings SHALL accept `off` and `rule` without a cuts file and SHALL refuse `shadow` and `on` for a point whose cuts file is not in the repository, with the error naming the point and the path.

#### Scenario: The table and the registry agree
- **WHEN** a test reads the table and the registry
- **THEN** the names and the cuts files of the two are equal

#### Scenario: On without a cuts file
- **WHEN** a test checks the mode `on` for a point of a table whose cuts file does not exist
- **THEN** the check fails and the error names the point and the file

#### Scenario: Shadow without a cuts file
- **WHEN** a test checks the mode `shadow` for a point of a table whose cuts file does not exist
- **THEN** the check fails and the error names the point and the file

#### Scenario: Rule without a cuts file
- **WHEN** a test checks the mode `rule` for a point of a table whose cuts file does not exist
- **THEN** the check passes without error

### Requirement: The registry bounds the series of its catalogue
The registry SHALL refuse a catalogue of points whose label sets of `devops_cli_decision_point_total` are more than `110`, the bound that `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` holds (`92` prior points plus `18` for `implement.extension`: `7` in `shadow`, `7` in `on`, `4` in `rule`). A point SHALL list the label sets that it can write across its supported modes.

#### Scenario: Too many points
- **WHEN** a test builds a catalogue whose label sets are more than `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`
- **THEN** the registry raises an error that names the bound that the constant holds

#### Scenario: The catalogue at the bound
- **WHEN** a test builds a registry whose label sets are at `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` (`110`)
- **THEN** the registry loads and its series count does not exceed `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`
