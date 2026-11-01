# Proposal

## Why

Issue #2965: each row of the roadmap Service is due on a multiple of 5 minutes. The poll is 300 s, and the rows are due every 10, 15 and 60 minutes (1440 for the alternatives row). After a restart or a slow round, the rows meet on one poll tick. Intake, refine and stage then wait for the model lane in one round, and the status rows read GitHub together. A person waits up to an hour for a plan or a refine.

## Feasibility

The Service budget stretches the poll when the requests of the last hour pass `service.github_requests_per_hour` (`budget.poll_interval`), so a shorter poll cannot pass the budget. The live use is about 990 of 2000 requests an hour (Prometheus, `devops_cli_github_requests_total`, 2026-11-01). A poll round reads the changes since the last success, so the request count of idle polls grows with the poll rate; the budget is the bound.

## Existing Tool Considered

No external tool covers this. The change edits integer constants in `defaults.py`, and the test checks them with the standard library.

## What Changes

- The default intervals are prime numbers and shorter: poll 151 s (was 300), metrics 13 min (15), implement 7 min (10), stage_ready 3 min (10), intake 29 min (60), refine 31 min (60), stage 37 min (60), alternatives 719 min (1440).
- A test fails when one of these defaults is not a prime or is a multiple of 5.
- The documents that state an interval name the new one.

## Capabilities

### Modified Capabilities

- `roadmap-alternatives`: the row is due every 719 minutes, not every 1440.

## Impact

- `src/devops_cli/config/defaults.py`, the docstrings in `roadmap/run.py` and `lang/en/help.py`, the generated command documents, ADR 0017, `docs/ROUTINE_TASKS.md`, `k8s/README.md`.
- A Service that runs with `service.poll_interval_seconds` set in `config.yaml` keeps that value until a person changes it.
