## ADDED Requirements

### Requirement: The linter reads the datasource of a target from its panel
The linter SHALL read the datasource type of a target from the target when the target declares one, and from its panel otherwise. It SHALL validate a target as PromQL only when the resolved datasource is the Prometheus one.

#### Scenario: A Pyroscope target with no datasource of its own
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose flame graph panel declares the Pyroscope datasource and whose target declares none
- **THEN** The report holds no empty-query error and no PromQL error for that target.

#### Scenario: A Loki target with no datasource of its own
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose logs panel declares the Loki datasource and whose target declares none
- **THEN** The report holds no empty-query error and no PromQL error for that target.

### Requirement: The linter checks the panels of a collapsed row
The linter SHALL run the panel id, target and datasource checks over each panel of a collapsed row, and SHALL count each of those panels in the panel count of its report. The overlap check SHALL read the top-level panels only.

#### Scenario: A duplicate panel id inside a collapsed row
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose collapsed row holds a panel with a duplicate panel id
- **THEN** The report holds an error for the duplicate panel id, and its panel count includes the nested panel.

### Requirement: A range variable in a graph target is an error
The linter SHALL report an error when a target of a time series, graph or bar chart panel that is not instant uses `$__range`.

#### Scenario: A range variable in a time series target
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose time series target uses `$__range` and is not instant
- **THEN** The report holds an error that names the dashboard, the panel and the target refId, and a copy that uses `$__rate_interval` lints clean.

### Requirement: A fixed window in a time series target is an error
The linter SHALL report an error when a target of a time series, graph or bar chart panel that is not instant holds a rate, irate, increase or delta over a window that is not `$__rate_interval` or `$__interval`, unless the target divides two such aggregates over one window, as a share or a burn rate does.

#### Scenario: A fixed rate window
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose time series target uses `rate(...[5m])`
- **THEN** The report holds an error that names the dashboard, the panel and the target refId, and a copy that uses `$__rate_interval` lints clean.

#### Scenario: A share keeps its window
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose time series target divides two increase aggregates over `[1h]`
- **THEN** The report holds no fixed-window error for that target.

### Requirement: A constant-zero fallback in a time series target is an error
The linter SHALL report an error when a target of a time series, graph or bar chart panel that is not instant contains `or vector(0)`.

#### Scenario: A constant-zero fallback
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose time series target contains `or vector(0)`
- **THEN** The report holds an error that names the dashboard, the panel and the target refId, and a copy without the fallback lints clean.

### Requirement: An unbounded label in a grouping or legend is an error
The linter SHALL report an error when a target of a time series, graph or bar chart panel names a label of the unbounded set in a `by()` clause or in its legend, the dashboard defines a template variable of that name, and the target holds no positive matcher for the label.

#### Scenario: An unbounded pod label
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard that defines a pod variable and whose time series target groups by pod or holds the pod label in its legend with no positive pod matcher
- **THEN** The report holds an error that names the dashboard, the panel and the target refId, and a copy that holds a positive pod matcher lints clean.

### Requirement: A histogram count on a seconds axis is an error
The linter SHALL report an error when a target of a time series panel holds `histogram_count`, the panel unit is `s` or `ms`, and no field override of the panel sets the unit of that refId.

#### Scenario: A histogram count with a seconds unit
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose time series target holds `histogram_count` in a panel with unit `s` and no override for its refId
- **THEN** The report holds an error that names the dashboard, the panel and the target refId, and a copy with a count unit or a refId override lints clean.

### Requirement: A Pyroscope target is checked by its label selector and profile type
The linter SHALL check a target of the Pyroscope datasource by its label selector and its profile type, SHALL report an empty one as an error, and SHALL NOT read the expression of that target.

#### Scenario: A Pyroscope target with no expression
- **WHEN** `uv run devops grafana dashboards lint` lints a dashboard whose Pyroscope target holds a label selector and a profile type and no expression
- **THEN** The report holds no empty-query error for that target, and it holds an error that names the panel when the label selector or the profile type is empty.

### Requirement: Each shipped dashboard lints clean
Each dashboard file of the environment tree and of the product base MUST lint clean, with no per-file and no per-rule exemption.

#### Scenario: The shipped dashboards lint clean
- **WHEN** `uv run devops grafana dashboards lint` runs with no path over both dashboard folders
- **THEN** It reports 0 errors and exits 0.

### Requirement: The new rules keep the dashboard lint test fast
The five query rules SHALL add less than 2 s to the dashboard lint test.

#### Scenario: New rules runtime
- **WHEN** the dashboard test times `_check_graph_queries` and `_check_histogram_units` alone over the 21 shipped dashboards
- **THEN** the total elapsed time of the two rule functions is less than 2 s.
