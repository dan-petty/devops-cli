# Design

## Decisions

- **Change `DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES` to 7 minutes**: 7 is a prime number not divisible by 5, satisfying architectural invariant #2965. It provides approximately 2.4 times the execution frequency of the previous 17-minute interval (~8.5 runs per hour versus ~3.5 runs per hour).
- **Update documentation, help strings, and tests synchronously**: Any change in default cadence values must reflect across the configuration reference, CLI reference, and tool snapshots.
- **Maintain backward compatibility through settings resolution**: Existing deployments setting `roadmap.refine.interval_minutes` explicitly retain their configured value.

## Rejected alternatives

- **Set interval to 5 or 6 minutes**: 5 is a multiple of 5, which architectural invariant #2965 explicitly refuses. 6 is not a prime number, which invariant #2965 also refuses.
- **Set interval to 3 minutes**: 3 minutes represents an almost six-fold increase in frequency (20 runs per hour), which is significantly higher than the requested three-fold increase.
