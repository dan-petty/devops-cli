# Proposal

## Why

After #2700 the dashboard repeated the panel `Telemetry: $sub_command` for each selected sub-command, so a sub-command that did not run in the range left a panel with no data. Issue #2703 asks to hide those panels with the v2 dashboard schema, the Auto grid and a has-data rule. #4707 replaced the repeated panel with one table, so the row shows only the sub-commands that have series and no empty panel is left to hide. The work that remains is to state and guard the answer: the dashboard keeps the classic schema that the sidecar's file provider loads, and a test fails if the file drifts toward v2.

## What Changes

- Set `schemaVersion` in `k8s/devops/dashboards/devops-cli.json` to 42, the value that the other Grafana 13 dashboards provisioned as files already state, so the file names the classic schema of Grafana 13 that the sidecar loads.
- Add `test_cli_dashboard_keeps_the_classic_schema` to `tests/grafana/test_grafana_dashboards.py`: it parses the dashboard and asserts a top-level `panels` array, no `apiVersion` key, and `schemaVersion` 42.
- Add the requirement "The devops-cli dashboard keeps the classic dashboard schema" to the `command-telemetry` capability through the spec delta of the change, so the archive writes the answer to #2703 into the living spec.
- Plan no v2 conversion, no Auto grid and no hide rule: the row "Sub-commands" holds one table with no `repeat` key, so no empty sub-command panel is left to hide.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: The devops-cli dashboard keeps the classic dashboard schema

## Impact

- Code: `k8s/devops/dashboards/devops-cli.json`
- Tests: `tests/grafana/test_grafana_dashboards.py`

## Feasibility

- The issue cannot be built as written. The probe of the path it cites answers: "The path `k8s/monitoring/dashboards/devops-cli.json` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/devops/dashboards/devops-cli.json`. Commit f31dc561 2026-11-12 refactor(k8s): split the product dashboards and rules in place (#5309) deleted or renamed it."
- `read_file` read the tail of `k8s/devops/dashboards/devops-cli.json`, and the probe answers "The path `k8s/devops/dashboards/devops-cli.json` is a file of the staging commit."
- The panel that the issue asks to hide repeats nowhere in the file: `search_code` for `"repeat"` returned no hit in `k8s/devops/dashboards/devops-cli.json`; its hits are `k8s/monitoring/dashboards/cloudnative-pg.json:3172: "repeat": "instances",`, `src/devops_cli/core/process.py:721: object.__setattr__(self, "repeat", repeat)` and `tests/grafana/test_grafana_dashboards.py:1156: p.get("repeat"),`.
- The row holds one table and a test guards it: `tests/grafana/test_grafana_dashboards.py:1142:def test_cli_dashboard_shows_the_selected_sub_commands_in_one_table() -> None:` asserts `tests/grafana/test_grafana_dashboards.py:1160:] == [("Sub-commands: calls, errors and latency in the range", "table", None, True)]`.
- The living spec already holds the one-table rule, so the plan adds no second one: `openspec/specs/command-telemetry/spec.md:200:The row "Sub-commands" SHALL hold one table and no panel that repeats.`
- The chart rule refuses a panel that repeats: `tests/prometheus/test_k8s_monitoring_dashboards.py:708: if "repeat" in panel:`, with the case `tests/prometheus/test_k8s_monitoring_dashboards.py:820: pytest.param({"repeat": "sub_command"}, "repeats", id="a repeat"),`.
- The staged file states `schemaVersion` 38 and no `apiVersion` key: `k8s/devops/dashboards/devops-cli.json:3418: "schemaVersion": 38,`; `search_code` for `"apiVersion":` returned no hit in a dashboard JSON file, and `search_code` for `dashboard.grafana.app` returned one hit, in `openspec/changes/archive/2026-10-29-2700-sub-command-dashboard/proposal.md:38:- The Auto grid layout with a "query has data" show/hide rule needs the v2 dashboard schema.`
- The Grafana 13 dashboards that the sidecar provisions as files state 42, and the archive of #5184 calls that shape the classic JSON: `k8s/monitoring/dashboards/devops-sre-service.json:1767: "schemaVersion": 42,`, `k8s/monitoring/dashboards/devops-roadmap-service.json:1740: "schemaVersion": 42,` and `openspec/changes/archive/2026-11-12-5184-build-service-dashboards-from-one-sre/proposal.md:38:the classic JSON that the dashboard sidecar provisions as files.`
- The home-grown builder writes `CONST_GRAFANA_SCHEMA_VERSION` 39: `src/devops_cli/config/constants.py:2407:CONST_GRAFANA_SCHEMA_VERSION: Final[int] = 39`, and `src/devops_cli/grafana/schema.py:131: schema_version: int = Field(default=CONST_GRAFANA_SCHEMA_VERSION, alias="schemaVersion")`; the plan states 42 and not 39, because the file is hand-kept and the provisioned Grafana 13 dashboards state 42.
- The `criteria` list is empty because the only `Acceptance criteria` heading of the issue body sits inside the `devops-roadmap-refine` block, and the body's own headings are `Problem or Motivation`, `Proposed Solution & Architectural Design`, `Target Subsystem` and `Existing Tool Considered`.
- The plan calls no function whose arguments need a checkout, a client or a network.
- The verify runs the `test` row of `devops ci` with `uv` and `devops` from the runner image and `pytest` from the image, over the workspace, with no network and no cluster; the plan introduces no command and no verify program, so it needs no failure class and no pod setting beyond the ones the pod already sets.
- First check against the real system: `uv run devops ci test tests/grafana/test_grafana_dashboards.py` runs the new guard and the existing dashboard tests offline.
- Second check against the real system: `uv run devops grafana dashboards lint` reports the lint result of the changed dashboard, the same on each run, from `src/devops_cli/commands/grafana.py:def dashboards_lint`.
- `read_issue` reports #2700 as closed (completed) and #4707 as closed (completed, released in v0.123.0), so the dependency the issue names is delivered and the repeated panel is gone.
- `find_issues` with the terms `devops-cli.json dashboard` listed ten open items, among them #4718 and #5192; no title of the ten names the top-level schema of the file, so the plan waits on none.

## Existing Tool Considered

grafana/grafana-foundation-sdk (https://github.com/grafana/grafana-foundation-sdk), Apache-2.0, last activity 2026-11-03, maintained. It covers the need in part: typed builders for the v2 dashboard model, AutoGrid and AutoGridItem builders, and conditional-rendering builders with a data condition. It gives no v2 file for this dashboard, converts no existing file and provisions nothing. The need is gone: #4707 replaced the repeated panel with one table, so no panel repeats, and this change adopts no tool and builds no code.

## Dependencies

None.
