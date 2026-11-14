# Design

## Decisions

- **Keep `k8s/devops/dashboards/devops-cli.json` on the classic schema and convert nothing to v2.**: The row "Sub-commands" holds one table with no `repeat` key, so no empty panel is left to hide, and no input of this run shows that the sidecar's file provider loads a Kubernetes-style v2 file.
- **State `schemaVersion` 42 in the dashboard, the value that the Grafana 13 dashboards provisioned as files state, and neither 38 nor the value of `CONST_GRAFANA_SCHEMA_VERSION`, 39.**: The sidecar loads the dashboards that state 42 today, and the archive of #5184 records 42 with a top-level `panels` array as the classic JSON that the sidecar provisions; 39 is the default of the home-grown builder, which this plan does not use.
- **Deliver the classic-schema rule with one `manifest` group that changes the dashboard file and the test together.**: The rule is a guard over the dashboard file, so the step changes the data that the test reads and the test that asserts it; a step that changed only test files would leave the guarded file untouched.
- **Add the requirement to `command-telemetry` and not to `devops-cli-dashboard`.**: `command-telemetry` already holds the content rules of this dashboard, including the one-table rule at `openspec/specs/command-telemetry/spec.md:200:The row "Sub-commands" SHALL hold one table and no panel that repeats.`, while `devops-cli-dashboard` holds the golden signals and the panel units.
- **Change only the top-level `schemaVersion` and add one test.**: The panels of the row "Sub-commands" already satisfy the one-table rule, and #4718 changes other panels of the same file, so a wider edit would collide with it.
- **Plan no cluster check of the file provider.**: The plan converts no file, so the question of a v2 file has no object, and this run checked no cluster.

## Rejected alternatives

- **Convert `k8s/devops/dashboards/devops-cli.json` to v2, put the sub-command row on an Auto grid and add a has-data hide rule.**: No panel of the file repeats: `search_code` for `"repeat"` returned no hit in it, and `tests/grafana/test_grafana_dashboards.py:1160:] == [("Sub-commands: calls, errors and latency in the range", "table", None, True)]` asserts one table with no repeat.
- **Probe the cluster with a Kubernetes-style v2 file and return the issue with the evidence of the file provider.**: The need is gone, so the probe decides nothing: `tests/prometheus/test_k8s_monitoring_dashboards.py:708: if "repeat" in panel:` refuses a panel that repeats, and `tests/prometheus/test_k8s_monitoring_dashboards.py:820: pytest.param({"repeat": "sub_command"}, "repeats", id="a repeat"),` covers the case.
- **Raise `schemaVersion` to the value of `CONST_GRAFANA_SCHEMA_VERSION`, 39.**: That constant is the default of the home-grown model at `src/devops_cli/grafana/schema.py:131: schema_version: int = Field(default=CONST_GRAFANA_SCHEMA_VERSION, alias="schemaVersion")`, while the provisioned Grafana 13 dashboards state 42 at `k8s/monitoring/dashboards/devops-sre-service.json:1767: "schemaVersion": 42,`.
- **Write a lint rule that refuses a dashboard file with an `apiVersion` key.**: The rule is a shape of one file, not a lint row, and the criterion's own scenario is a test that parses the dashboard file; the guard therefore belongs in `tests/grafana/test_grafana_dashboards.py`, beside `test_cli_dashboard_shows_the_selected_sub_commands_in_one_table`.

## Security

The change edits a Grafana dashboard file that the monitoring Application renders into a ConfigMap, and it adds no query, no datasource, no label and no manifest setting, so no credential, token or network rule crosses a trust boundary. A person confirms that the dashboard still loads in Grafana 13 through the sidecar's classic file provider, with the panels and the datasources that the staged file has. The test `test_cli_dashboard_keeps_the_classic_schema` fails if the file gains an `apiVersion` key, loses its top-level `panels` array or changes its schema version, and `test_cli_dashboard_shows_the_selected_sub_commands_in_one_table` fails if a panel repeats.
