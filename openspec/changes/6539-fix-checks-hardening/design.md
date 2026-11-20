# Design

## Decisions

- The calls go in the command, right after `require_runner`, as `apply_implement` places them. `job_repair` stays free of kernel calls, so the repair tests do not change the test process.

## Rejected alternatives

- Call them in `job_repair`: each repair test would then need a spy for the kernel calls.
