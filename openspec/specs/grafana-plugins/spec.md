# grafana-plugins Specification

## Purpose
The plugins that the Grafana of the monitoring stack installs at start, and the version of each plugin that git holds.

## Requirements

### Requirement: Grafana pins each Drilldown app at its release for Grafana 13
The Grafana values SHALL pin each of the apps `grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, `grafana-pyroscope-app` and `grafana-exploretraces-app` at a final 3.x release, in the chart's `plugins` value, as `<id>@<version>`. Each 3.x release needs Grafana 13.1.0 or later.

#### Scenario: The four apps have a pin
- **WHEN** the Grafana values are read
- **THEN** the `plugins` value has an entry `<id>@<version>` for each of the four apps, and each version is a final release with the major number 3

### Requirement: Renovate reads each Grafana plugin pin
The Renovate configuration SHALL have a regex custom manager that matches only `k8s/monitoring/grafana-values.yaml` and reads each `- <id>@<version>` entry of its `plugins` value, with a custom datasource whose `defaultRegistryUrlTemplate` is `https://grafana.com/api/plugins/{{packageName}}/versions` and `semver` versioning.

#### Scenario: The manager reads the four pins
- **WHEN** a test applies the manager's match strings to `k8s/monitoring/grafana-values.yaml`
- **THEN** the matches are the `plugins` entries, each with its plugin ID and version, and nothing else

#### Scenario: The datasource reads grafana.com
- **WHEN** a test reads the manager's `datasourceTemplate` and the custom datasource it names
- **THEN** the datasource reads `https://grafana.com/api/plugins/{{packageName}}/versions` as JSON with one JSONata transform of `items`

### Requirement: Each plugin update is its own pull request below the next major
The Renovate configuration SHALL give each Grafana plugin update the labels `type/chore`, `scope/deps` and `scope/infra`, allow only versions below the major after the pinned one, put each plugin in its own pull request, and add a pull request note that names `grafanaDependency` and links the record of the proposed release.

#### Scenario: The plugin rule
- **WHEN** a test reads the package rule that matches the plugin datasource, and the rule that labels the custom managers of `k8s/`
- **THEN** its `allowedVersions` is `<4.0.0` for pins of major 3, it sets no `groupName`, and a note names `grafanaDependency` and links `https://grafana.com/api/plugins/{{{depName}}}/versions/{{{newVersion}}}`
- **AND** the preset labels are `type/chore` and `scope/deps`, and the custom managers of `k8s/**` add `scope/infra`

### Requirement: Grafana preinstalls the LLM app plugin
The Grafana values SHALL include `grafana-llm-app` pinned at release 1.2.0 in the chart `plugins` value as `grafana-llm-app@1.2.0`. The 1.2.0 release is compatible with Grafana 13 (`>=13.0.0-0`).

#### Scenario: The LLM app plugin has a pin
- **WHEN** the Grafana values are read
- **THEN** the `plugins` value contains `grafana-llm-app@1.2.0`

### Requirement: Grafana provisions grafana-llm-app for LiteLLM gateway
The Grafana values SHALL configure `extraConfigmapMounts` and `extraObjects` to provision `grafana-llm-app` at `/etc/grafana/provisioning/plugins/apps.yaml`. The provisioning file SHALL configure provider `openai`, url `http://llm-gateway.llm.svc.cluster.local:4000/v1`, models `qwen3.8:27b`, and API key `$__env{GF_LLM_GATEWAY_KEY}`. The values SHALL map `GF_LLM_GATEWAY_KEY` to Secret `grafana-admin` key `llm-gateway-key`.

#### Scenario: Plugin provisioning in Grafana values
- **WHEN** `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `extraConfigmapMounts` mounts `apps.yaml` to `/etc/grafana/provisioning/plugins/apps.yaml`
- **AND** `extraObjects` defines ConfigMap `grafana-llm-plugin` targeting LiteLLM gateway and `qwen3.8:27b`
- **AND** `envValueFrom` maps `GF_LLM_GATEWAY_KEY` to `grafana-admin` `llm-gateway-key`

### Requirement: Grafana enables the dashgpt feature toggle
The Grafana values SHALL enable the `dashgpt` feature toggle under `grafana.ini.feature_toggles.enable` in `k8s/monitoring/grafana-values.yaml`.

#### Scenario: Feature toggle in Grafana values
- **WHEN** `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `grafana.ini.feature_toggles.enable` contains `dashgpt`
