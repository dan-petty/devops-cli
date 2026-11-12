# Design

## Decisions

- The value holds the state; no label does. A gauge keeps one series for each service, and for each service and component, so a new status replaces the old value.
- The status panels read `[1h]`, not `[$__range]`. A status is a fact about now: a value of 10 days ago is not the current status. The Service sends the status at each metrics round, and one hour holds several rounds.
- The panels add no `max(`. A second series in the last hour then shows as a second value, so a second sender is visible and is not hidden.
- The component gauge gets the same fix in the same pull request: the cause is the same, in the same function.

## Rejected alternatives

- Keep the labels and take `topk(1, timestamp(...))` in the panel: the panel works, but each change of the indicator still makes a new series, and every other reader must repeat the trick.
- Send a 0 for each indicator that is not current: it keeps 4 series for each service and 4 for each component, which is more series for the same fact.
