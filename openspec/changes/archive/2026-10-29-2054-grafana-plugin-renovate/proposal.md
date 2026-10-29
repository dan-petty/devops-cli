# Proposal

## Why

Issue #2054: #2022 pins the four Grafana Drilldown apps at `<id>@3.0.0` in the `plugins` value of `k8s/monitoring/grafana-values.yaml`. `.github/renovate.json` has no manager for Grafana plugins, so no pull request proposes a new release, and the pins stay at 3.0.0.

## What Changes

- `.github/renovate.json` gets a custom datasource, `grafana_plugins`. It reads `https://grafana.com/api/plugins/{{packageName}}/versions` as JSON, and a JSONata transform maps each entry of `items` to a release: `version`, `releaseTimestamp` from `createdAt`, and `isDeprecated` when `status` is not `active`.
- A regex custom manager reads the `- <id>@<version>` entries of `k8s/monitoring/grafana-values.yaml` only, with that datasource and `semver` versioning.
- A package rule gives each plugin update the `type/chore` and `scope/infra` labels, holds it below the next major (`<4.0.0`, the major that the existing Grafana 13 test requires), and adds a pull request note. The note links the release's record, `https://grafana.com/api/plugins/<id>/versions/<version>`, and asks the reviewer to check its `grafanaDependency` against the Grafana image of the `grafana` chart. Each plugin gets its own pull request.
- `docs/SDLC.md` and the comment above the pins describe the manager.
- The change adds a Renovate behavior that a person sees as pull requests, so it carries a spec delta: ADDED requirements in `grafana-plugins`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `grafana-plugins`: Renovate proposes each new release of a pinned plugin.

## Impact

- `.github/renovate.json`, `k8s/monitoring/grafana-values.yaml` (a comment), `docs/SDLC.md`.
- `tests/test_renovate_config.py`.

## Feasibility

- The datasource exists for this use. Renovate's documentation of the custom datasource (docs.renovatebot.com/modules/datasource/custom/, read 2026-10-29) names `defaultRegistryUrlTemplate`, `format: json` and JSONata `transformTemplates`, and a regex manager that names `custom.<name>` in `datasourceTemplate`. The result must hold a `releases` list whose entries have `version`; `releaseTimestamp` and `isDeprecated` are allowed. The page documents no per-release `constraints`.
- The API answers as the transform expects. `https://grafana.com/api/plugins/<id>/versions` returned `items` for each of the four apps (65, 61, 65 and 31 entries), each with `version`, `createdAt`, `status` and `grafanaDependency`. The transform, run with JSONata 2 on the saved lokiexplore reply, gave 65 releases, the newest `3.1.0`; a one-item reply also gave a list.
- The API cannot filter by Grafana version. Any query parameter, also `grafanaVersion=13.2.4`, returned an empty `items` list.
- The risk is real now. The running Grafana is `13.2.4` (chart 14.0.1). The 3.1.0 releases need `>=13.2.0-0` (lokiexplore, exploretraces), `>=13.1.0-0` (pyroscope) and `>=13.3.0-0` (metricsdrilldown). So a pull request for metricsdrilldown 3.1.0 must wait for a Grafana 13.3 image, while the other three can merge. That is why each plugin gets its own pull request, and why the note links the release record.
- The match string matches the four pins and nothing else of the values file, in Python (the test) and in JavaScript (`node`, run on the file). Renovate's `renovate-config-validator` was not run: this session's permissions refused to run the downloaded Renovate package. The Renovate App validates the configuration on its next run and opens a configuration error issue when it fails.

## Existing Tool Considered

Renovate covers the need with its own custom datasource and regex manager; the change builds no version checker and deletes no code. The Grafana compatibility check stays a person's step in review, because neither Renovate's custom datasource nor the grafana.com API can filter releases by `grafanaDependency`.
