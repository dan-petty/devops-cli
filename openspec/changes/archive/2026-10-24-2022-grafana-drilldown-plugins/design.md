# Design

## Context

Grafana runs from the chart grafana-community/grafana 14.0.1 with the values in `k8s/monitoring/grafana-values.yaml`. It keeps its plugins and its SQLite database on the `grafana` volume. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Git holds the version of each Drilldown app, and Grafana installs that version at start.

**Non-Goals:**

- An automatic proposal for a new release of a pinned app. The four pins stay at 3.0.0 until a pull request changes them.
- The other preinstalled plugins. `grafana-advisor-app` is at 1.1.0, its newest release, which needs Grafana 13.2.0 or later.

## Decisions

- **Pin each app in the chart's `plugins` value.** This is the documented value of the chart, and Grafana installs a pinned version that is not the installed version.
- Rejected: set `preinstall_auto_update` to true. Grafana then calls `CanUpdateVersion` with `onlyMinor` true, which skips a new major version (`pkg/services/pluginsintegration/pluginchecker/service.go` in v13.2.4). Thus the apps stay at 2.x, and git still holds no version.
- Rejected: an entry with a download URL (`<id>@<version>@<url>`). The URL repeats the ID and the version, so a new release must change two values that must agree. The catalog install gets the same release from grafana.com.
- Rejected: `[plugins] preinstall` in `grafana.ini`, which installs in the background. A failed install then gives only a log line, and Grafana runs without the pinned version. A sync install that fails stops the start, so the failure is clear.

## Risks / Trade-offs

- [grafana.com is unavailable at the first start after the change] → The sync install fails and stops the start, and the pod starts again until the install completes. After the install, the pinned version is the installed version, and a start makes no request for the four apps.
- [A new release of an app comes out] → The pin keeps 3.0.0 until a pull request changes it. Renovate does not track Grafana plugins.

## Migration Plan

Argo CD syncs the values from `main`. The new `checksum/config` restarts Grafana one time, and the `Recreate` strategy stops the old pod first. At start, Grafana removes each 2.x app and installs the 3.0.0 release. To roll back, revert the commit: Grafana then keeps the 3.0.0 apps on the volume, because the chart turns off the automatic update.
