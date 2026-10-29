# Design

## Decisions

- **One pull request for each plugin.** The four apps release together, but their releases need different Grafana minors: today metricsdrilldown 3.1.0 needs Grafana 13.3.0 and the other three need 13.2.0 or less. A grouped pull request would hold three safe updates behind one that the running Grafana cannot install.
- **Held below the next major.** `allowedVersions: "<4.0.0"` keeps the major that `tests/test_k8s_monitoring_integration.py` (`GRAFANA_13_DRILLDOWN_MAJOR = 3`) and the `grafana-plugins` spec require for Grafana 13. A move to Grafana 14 changes the test, the spec and this rule together.
- **A note that links the release record.** The note names `https://grafana.com/api/plugins/{{{depName}}}/versions/{{{newVersion}}}`, which returns that release's `grafanaDependency`.

## Rejected alternatives

- **Renovate constraint filtering (`constraintsFiltering: strict`).** The custom datasource's documented result has no per-release `constraints`, so Renovate cannot read `grafanaDependency`.
- **A server-side filter.** `https://grafana.com/api/plugins/<id>/versions?grafanaVersion=13.2.4` returned no entries; the API returns an empty list for any query parameter.
- **A JSONata filter with the Grafana version written in the transform.** The Grafana version comes from the `grafana` chart, which Renovate also updates, so a version written in `renovate.json` would drift from the chart without a check.
- **A grouped pull request for the four apps.** See the first decision.
- **A CI job that reads `grafanaDependency` for each pin.** It needs the network and the chart's Grafana version; it is outside this item, which asks only for the Renovate proposal.
