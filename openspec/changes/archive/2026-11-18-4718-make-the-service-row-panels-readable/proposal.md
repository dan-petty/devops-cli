# Proposal: make the Service row panels readable

## Why
The Service row in the roadmap service telemetry dashboard was difficult to read.
Several panels used raw counters without rate or increase functions.
Some panels lacked descriptive titles and units.
In addition, the AI RAG dashboard spend and planner tool panels needed clearer layouts and units.

## What Changes
- Add an error share time series panel to the Service row.
- Convert raw service counter queries to rate or increase queries.
- Format all panel titles to use the standard "Signal: measure" pattern.
- Assign appropriate units, legends, and minimum limits to each panel.
- Update the AI RAG dashboard spend panels and tool call panels.
- Add Prometheus test cases to verify the dashboard queries.

## Capabilities
- Operators can read service health and error rates quickly.
- Operators can monitor AI spend and tool call character counts.

## Impact
- Improves dashboard readability during incidents.
- Does not change service code or metrics definitions.

## Feasibility
- Verified with Grafana dashboard linters and Promtool query tests.
- All test fixtures pass with expected samples.

## Existing Tool Considered
- Grafana dashboard JSON models and Promtool rule testing provide built-in validation.
- No external tool is required.
