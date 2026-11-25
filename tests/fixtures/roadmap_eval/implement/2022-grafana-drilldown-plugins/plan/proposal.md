# Proposal

## Why

Issue #2022: Grafana keeps its four Drilldown apps on its volume at 2.x. These apps are `grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, `grafana-pyroscope-app` and `grafana-exploretraces-app`. #1624 moved Grafana to the chart grafana-community/grafana 14.0.1, which runs Grafana 13.2.4. That chart sets `[plugins] preinstall_auto_update` to false, so Grafana does not update a preinstalled app. The Grafana 13 upgrade guide tells users to update every plugin for React 19. The 3.0.0 release of each app is the newest release, and each one needs Grafana 13.1.0 or later.

## What Changes

- The chart's `plugins` value in `k8s/monitoring/grafana-values.yaml` pins each of the four apps at 3.0.0, in the format `<id>@<version>`. The chart writes the list to `GF_PLUGINS_PREINSTALL_SYNC`. At start, Grafana installs each pinned version that is not the installed version, and the version is in git.
- A test fails when one of the four apps has no pinned final release with the major number 3.
- The values are a manifest, and the plugins that Grafana runs are observable. Thus the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `grafana-plugins`: the plugins that the monitoring stack's Grafana installs, and the versions that git holds for them.

### Modified Capabilities

None.

## Impact

- Manifest: `k8s/monitoring/grafana-values.yaml`. The rendered chart gets the `plugins` key in the `grafana` ConfigMap, the variable `GF_PLUGINS_PREINSTALL_SYNC` in the Deployment, and a new `checksum/config`. Thus Argo CD restarts Grafana one time. With the `Recreate` strategy, Grafana stops while the new pod installs the four apps. The SQLite database on the `grafana` volume does not change.
- Tests: `tests/test_k8s_monitoring_integration.py`.

## Feasibility

- On 2026-10-24, the live Grafana `GET /api/health` gave version 13.2.4. `GET /api/plugins?type=app` gave `grafana-lokiexplore-app` 2.6.0, `grafana-metricsdrilldown-app` 2.5.1, `grafana-pyroscope-app` 2.3.1 and `grafana-exploretraces-app` 2.2.1. `GET /api/plugins/errors` gave no errors.
- `https://grafana.com/api/plugins/<id>/versions` gave 3.0.0 as the newest release of each app, each with `grafanaDependency` `>=13.1.0-0`. The 3.0.0 changelog of each app lists the change to Grafana 13.1.0 or later as a breaking change. The Grafana pod reached grafana.com: `GET /api/gnet/plugins/grafana-lokiexplore-app/versions/3.0.0` through Grafana gave this release.
- `helm show values grafana-community/grafana --version 14.0.1` sets `grafana.ini.plugins.preinstall_auto_update: "false"` and documents `plugins` as a list of plugin IDs, with an optional `@<version>@<url>`. The chart's `_config.tpl` joins the list with commas into the ConfigMap key `plugins`, and `_pod.tpl` sets `GF_PLUGINS_PREINSTALL_SYNC` from that key.
- The Grafana v13.2.4 source confirms the effect. `pkg/setting/setting_plugins.go` splits each entry on `@` into ID, version and URL. `pkg/services/pluginsintegration/plugininstaller/service.go` installs a pinned version that is not the installed version, and stops the start when a sync install fails. `pkg/plugins/manager/installer.go` then removes the installed version and installs the pinned version from the catalog.
- `helm template` of the chart with the base values gave the `checksum/config` of the live Deployment. With the change, the rendered chart changed only in the three places that Impact names.
- On the base commit, `test_grafana_pins_each_drilldown_app_at_its_release_for_grafana_13` failed: each of the four apps had no pinned version.

## Existing Tool Considered

Grafana's plugin preinstall, through the chart's documented `plugins` value, installs and pins the apps. Nothing is built. The change sets one chart value and adds one test that reads the committed values. It deletes no internal code.
