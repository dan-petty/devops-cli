# Design

## Decisions

- **Use the existing emit() and InstrumentKind.GAUGE path for both gauges.**: The project metrics already use this path, and the issue names it as the existing tool.
- **Send the gauges at the Service's existing log points, not in a new timer or hook.**: The issue says sent where the Service already logs the values, and the values are already computed at those points.
- **No labels on either gauge.**: The issue names no labels, and the Service context already provides the identifying attributes.

## Rejected alternatives

- **Add the gauges to a new telemetry module.**: The existing emit() path in instruments.py already handles gauges, and the project metrics use it. A new module would duplicate the path.
- **Use a counter for the pause end time.**: The pause end time is a snapshot, not an accumulation. A gauge is the correct kind, and the issue names it as a gauge.
