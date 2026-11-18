# Design

## Decisions
- Rename the one processor key and its pipeline entry to `delta_to_cumulative`. A second old key
  beside the new one keeps the deprecation warning and adds an unused processor.
- Keep the metric name `otelcol_deltatocumulative_datapoints` in the dashboard and the documents. A
  local run of `otel/opentelemetry-collector-contrib:0.163.2` with the renamed key showed the
  deprecation warning gone and the internal metric still named `otelcol_deltatocumulative_*`: the
  processor registers its telemetry under the old type, so the metric name does not follow the key.
- Rename the processor name in the dashboard title and description and in the prose of the
  documents, and change the config, the code comments, the tests and the two specs in one pull
  request, so no check or document names the old key.

## Rejected alternatives
- Keep `deltatocumulative`: the old name logs a deprecation warning and stops the metrics pipeline
  when a later collector removes the alias.
- Keep both processor keys: the old alias still warns, and the pipeline uses one processor.
- Change the config only: the tests, the dashboard and the documents would still name the old key.
- Rename the metric `otelcol_deltatocumulative_datapoints` in the dashboard and the documents: the
  collector keeps the old metric name, so the renamed query would match no series.
- Follow up in a second pull request: the old name stays in the tests and the documents after the
  config changes, and the checks fail on the drift.
