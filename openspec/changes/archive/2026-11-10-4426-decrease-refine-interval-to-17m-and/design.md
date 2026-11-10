# Design

## Decisions

### Decision 1: Use 17 Minutes as Prime Interval

The hourly jobs in `src/devops_cli/config/defaults.py` use prime-number intervals to avoid collisions (intake is 29, metrics is 13, stage is 37).
17 is a prime number that reduces the waiting interval between refine runs from 31 minutes while keeping runs asynchronous with 5-minute ticks.

### Decision 2: Raise Limit to 7 Items

The previous default limit of 3 items caused backlogs of New items to clear slowly.
Raising the default to 7 items increases throughput per round while keeping model calls within manageable latency bounds.

### Decision 3: Record Raised Limit in Limit Registry

In `tests/roadmap/test_roadmap_limit_classes.py`, limits that increase are classified as `"raised"` with a description citing the previous value (`"was 3; items of one round"`).

## Rejected alternatives

### Rejected Alternative 1: Reducing Interval Below 10 Minutes

Running refine faster than 10 minutes risks overlapping Service runs and exceeding GitHub rate limits during high issue activity.

### Rejected Alternative 2: Unlimited Batch Size

Processing all New items without a limit would cause prolonged Service runs, exceed timeout budgets, and risk API quotas.
