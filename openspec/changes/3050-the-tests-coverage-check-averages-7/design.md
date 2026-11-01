# Design

## Decisions

- **Enable uv cache and parallel workers in the test job**: The 56-interpreter startup cost (#2369) and per-worker repetition (#2371) are the dominant time sinks. Caching removes the repeated start-up. Parallel workers reduce wall-clock time without removing tests.
- **Extend the Test Job Duration window from 10 to 20 runs**: The acceptance criterion in #3050 states the average over 20 runs of main. The current window of 10 is too small to give a stable mean.
- **Keep the Tests & Coverage job name and required check unchanged**: ADR 0004 pins the job names. The owner rule of 2026-10-23 forbids removing or weakening a required check.

## Rejected alternatives

- **Remove or skip slow tests to reduce duration**: The owner rule of 2026-10-23 forbids skipping a check. ADR 0004 requires the full suite to run authoritatively.
- **Rely on manual measurement of the 5-minute bound**: The acceptance criterion requires a job that fails the build when the average exceeds 300 seconds. Manual measurement does not fail the build.
