# Design

## Decisions

- **A case file is a promtool unit test file with keys added.** A test group adds `shape`. A `promql_expr_test` case adds `panel`, `ref_id` and `variables`. The test removes these keys before it runs promtool, because promtool refuses a key it does not know. A person who knows promtool unit tests can read a case with no new format.
- **The case holds the query as the dashboard holds it.** A separate test compares `expr` with the query of the target. A change of a covered query then fails until its cases change, and this test does not need promtool, so it runs on every host.
- **The case gives `__range` and `__interval` as durations; the test calculates the other range and interval variables.** Grafana writes them in seconds (`86400s`). `$__rate_interval` uses the Min step of the target, else the `timeInterval` of the data source in `grafana-values.yaml`, as the Grafana documentation says. A case that gives a calculated variable fails, so two values cannot disagree.
- **A variable with no value stays in the query, and the test then fails with its name.** The test also leaves a format other than `raw` and a field path, because the harness does not copy the formats of Grafana.
- **One promtool run for each dashboard.** The test writes one file under `tmp_path` and runs `promtool test rules` once, so the time grows with the number of dashboards, not of cases.
- **The cases of the first file cover panels that are correct today.** "AI Spend in Range" covers the three counter shapes, and "Alternatives Unchecked Items" covers the snapshot gauge. The dashboard items of #4675 add the cases of the panels that they change.
- **Each series ends at the evaluation time.** The increase of a series that ends before the end of the range has an extrapolation of half a sample interval. The cases of panels that are correct today keep their expected values exact, and comments give the sum from the series.

## Rejected alternatives

- **Read the query from the dashboard and keep no `expr` in the case.** Then a change of a covered query changes what the case evaluates with no change in the case, and a wrong change can pass. Acceptance criterion 2 of #4680 asks for a failure that names the dashboard, the panel and the refId.
- **Run each case in its own promtool process.** Each run costs 1 s to 2 s on the devcontainer, so the test time grows with each case. One run for each file keeps the test under 10 s.
- **A Prometheus server in a container with backfilled series.** This needs a container engine on the runner, and promtool already evaluates PromQL on series in its unit test format.
