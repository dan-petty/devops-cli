# Design

## Decisions

- **The limits are twice the code defaults.** A test compares each value with two times its `DEFAULT_` constant, so a later change of a default shows in the test.
- **The item time stops at the ceiling.** Twice the default item time (12600 s) is above the 14400 s ceiling of the Job deadline, so the template sets 14400 s.
- **The scheduling keys stay out.** The `backlog_*` keys make the rows poll more often. The Service is at its GitHub budget now, so more polls would stop more rounds.
- **The planner tests read `stage`.** The planner reads the task `stage`, which has its own entry. The trial of the local model in `analysis` does not move it.

## Rejected alternatives

- **Raise the code defaults.** The doubled limits are a choice for this cluster while the jobs are under 80%, not a default for every install.
- **Keep the limits in the live ConfigMap only.** A deploy removes them, as it did between 2026-11-14 and 2026-11-15.
