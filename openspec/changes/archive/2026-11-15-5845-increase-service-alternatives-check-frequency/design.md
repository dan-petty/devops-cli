# Design

## Decisions

- **Change `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` to 239 minutes**: 239 is a prime number not divisible by 5, satisfying architectural invariant #2965. It provides approximately three times the execution frequency of the previous 719-minute interval (~4 hours versus ~12 hours).
- **Update documentation, help strings, dashboards, and tests synchronously**: Any change in default cadence values must reflect across the configuration reference, CLI reference, and dashboard descriptions.
- **Maintain backward compatibility through settings resolution**: Existing deployments setting `roadmap.alternatives.interval_minutes` explicitly retain their configured value.

## Rejected alternatives

- **Set interval to 240 minutes**: Rejected because 240 is not a prime number and is divisible by 5, violating invariant #2965.
- **Set interval to 233 minutes**: While 233 is prime, 239 is closer to the exact one-third value of 719 (719 / 3 = 239.67).
