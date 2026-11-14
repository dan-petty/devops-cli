# Design

## Decisions

- **Include `P0-Critical` in `CONST_ROADMAP_MODEL_PRIORITIES`.** The structured output schema of `proposal_schema` generates an enum from `CONST_ROADMAP_MODEL_PRIORITIES`. Adding `P0-Critical` enables both the triage model and Jev to return `P0-Critical`.
- **Remove priority capping in `_priority_choice`.** Previously, `_priority_choice` capped any `P0-Critical` proposal to `P1-High`. With explicit criteria, a proposed `P0-Critical` stands. Normalize bare `"P0"` to `"P0-Critical"`.
- **Define explicit criteria in `roadmap_intake_system.md` and `CONST_ROADMAP_JEV_PRIORITY_CRITERIA`.**
  - `P0-Critical`:
    - Issue causing user-facing problems on a website or a service
    - Anything causing data corruption
    - Problems causing violations of the SLI/SLO thresholds for SRE standards
    - Live critical security vulnerabilities or issues
    - Any issue causing service jobs to fail
    - Any issue that is blocking another P0 issue
    - Any issue causing CI to fail or be very slow
  - `P1-High`:
    - Any issues causing increased error rates or performance degradation
    - Any issues causing increased need for retries or multiple attempts
    - Any issue causing increased AI spend without an equivalent benefit to the performance of the task
    - Any issue blocking another P1 issue
    - Live high security vulnerabilities or issues
  - `P2-Medium`: Standard defect, gap, or backlog item with no immediate blocker or deadline
  - `P3-Low`: Small improvement or idea that nothing waits for
- **Preserve verified evidence handling.** If an issue cites verified evidence (advisory GHSA, failed run ID, regression commit SHA), intake verifies it as before. When valid, it confirms `P0-Critical`.

## Rejected alternatives

- **Keep P0 manual-only or evidence-only.** Rejected: The owner explicitly directed that issues meeting these operational and stability criteria are labeled P0 as they are being labeled.
- **Implement a separate post-intake labeling hook.** Rejected: Intake is the single entry point for setting Priority labels on candidates. Adding a separate hook duplicates logic and increases round latency.
