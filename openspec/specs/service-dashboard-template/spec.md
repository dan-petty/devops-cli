# service-dashboard-template Specification

## Purpose
The SRE template that builds the Grafana dashboard of a Kubernetes service from a spec of the `services.toml` of the environment tree: its layout, units, series, colors and variables, and the build that writes each dashboard next to its spec file.

## Requirements

### Requirement: The template lays out the SLO row, the golden signals and the collapsed rows
`service_dashboard` SHALL build a classic dashboard of schema version 42 from a `ServiceSpec`, in the layout of docs/DESIGN.md: the 4 SLO tiles (`w6 h4`), the burn rate and the budget left (`w12 h8`), the golden signals latency, traffic, errors and saturation (`w12 h8`), then the collapsed rows "Capacity", "Logs" when the spec has logs, and "Profiles" when it has profile types.

#### Scenario: The layout of a fixture spec
- **WHEN** the test builds the dashboard of a spec with logs and one profile type
- **THEN** the top-level panels have the types, title prefixes and grid positions of the layout, and the last three rows are collapsed

#### Scenario: A spec with no logs and no profiles
- **WHEN** the spec has `logs = false` and no profile type
- **THEN** the rows are the SLO row, "Golden signals" and "Capacity"

### Requirement: Each panel has one unit, a sentence-case title and a description
Each panel SHALL have a title "Signal: measure" in sentence case and a description. Each time series and stat SHALL have one unit, and no override SHALL set a second unit.

#### Scenario: The panels of a build
- **WHEN** the test reads each panel of a build, the panels of the collapsed rows included
- **THEN** no panel breaks a rule

#### Scenario: A broken panel
- **WHEN** a panel has a title in title case, no description and an override that sets the unit `s`
- **THEN** the check reports the three problems

### Requirement: A time series draws at most 3 series and Other
Each time series SHALL have at most 3 targets that are not constants, each with a fixed legend name.

#### Scenario: The time series of a build
- **WHEN** the test reads the 8 time series of a build
- **THEN** none has more than 3 data series or a legend with a label template

### Requirement: The burn rate shows each window against its page line
The burn-rate chart SHALL have y min 0 and the unit `x`, the 1 h and 6 h burn rates as series 1 and 2, and the constant lines of the page lines and the 1x pace. A page line SHALL be `share x window days x 24 / window hours`, with the share 2 % for 1 h and 5 % for 6 h. Each constant line SHALL be `red` or `text` with the line style `dots`, and each time series SHALL have the fill opacity 0.

#### Scenario: An SLO window of 30 days
- **WHEN** the test reads the burn-rate chart of a spec with a window of 30 days
- **THEN** the constant lines are `vector(14.4)` and `vector(6)` in `red` and `vector(1)` in `text`, each dotted

#### Scenario: An SLO of 99 % over 28 days
- **WHEN** the spec has the target 0.99 and a window of 28 days
- **THEN** the page lines are `vector(13.44)` and `vector(5.6)`, and the 1 h burn rate divides by 0.01

### Requirement: The SLO queries give the SLI, the budget and the burn rate
The SLI SHALL be one minus the share of failed requests in the SLO window, the budget left one minus that share over the budget, and the burn rate of a window that share over the budget. With requests and no failed request, the failed count SHALL be the zero of the requests. With no request, the queries SHALL give no value.

#### Scenario: 1,000 requests with 2 failed and an SLO of 99 %
- **WHEN** promtool evaluates the queries of the build of `tests/fixtures/dashboard_queries/service-template.yaml` on 1,000 requests, 2 of them failed
- **THEN** the SLI is 0.998, the budget left is 0.8 and the burn rate of each window is 0.2

#### Scenario: Requests and no failed request
- **WHEN** the requests have no counter of a failed code
- **THEN** the SLI is 1, the budget left is 1 and the burn rate is 0

### Requirement: The colors are token hex or Grafana color names
Each color of a service dashboard SHALL be the token hex of `color.data.cat.1` or `color.data.cat.2`, which pass 3:1 on the four Grafana backgrounds, or one of the Grafana names `text`, `semi-dark-orange` and `red`. Each color mode SHALL be `fixed`, `thresholds`, `shades` or `continuous-cividis`. The template source SHALL hold no hex color.

#### Scenario: The committed dashboards and a fixture build
- **WHEN** the test reads each color of the committed service dashboards and of a fixture build
- **THEN** the check reports no color

#### Scenario: A palette color
- **WHEN** a dashboard holds the mode `palette-classic`, the hex `#73bf69`, the name `green` and the light hex of `color.data.cat.3`
- **THEN** the check reports each of them

### Requirement: A generic spec selects one namespace and one workload
A spec with `variables` SHALL give the dashboard the single-value query variables `namespace` and `workload` on the values of the spec, and its queries SHALL read them. A spec without them SHALL put its namespace and workload in place of the variables.

#### Scenario: Both kinds of spec
- **WHEN** the test builds a spec with variables and one without
- **THEN** the first has the variables `namespace` and `workload` with `multi` and `includeAll` false, and the second has no variable and no `$namespace` or `$workload`

### Requirement: The log row shows the warnings above all lines of the workload pods
The log row of a service dashboard SHALL hold "Logs: warnings and errors" (`h8`) above "Logs: all lines" (`h12`), on the `loki` data source. The query of all lines SHALL be `{namespace="<namespace>"} | pod=~"<workload>-[a-z0-9]+-[a-z0-9]+"`, and the warnings query SHALL add `| detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"`.

#### Scenario: The log row of a fixture build
- **WHEN** the test reads the panels of the row "Logs" of the build of the namespace `shop` and the workload `cart`
- **THEN** the two panels have these titles, queries and heights, in this order

### Requirement: The template build writes each dashboard next to its spec file
The `main` of `devops_cli.grafana.service_dashboard` SHALL write `<uid>.json` next to the spec file that it gets, for each spec of the file.

#### Scenario: A build into a folder
- **WHEN** `main` runs on a spec file with one spec in an empty folder
- **THEN** the folder holds the spec file and `<uid>.json`, which is the build of the spec
