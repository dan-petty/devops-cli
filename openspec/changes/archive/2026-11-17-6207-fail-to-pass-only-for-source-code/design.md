# Design

## Decisions
- One predicate, `is_source_code`, beside `is_test_file` and `is_gate_check`. The stage imports it, as the implement step already imports `is_test_file`.
- The report gets `needs_proof`, true by default, so a report that another caller builds keeps today's verdict. `run_fail_to_pass` sets it false when the diff holds no source code and no gate check, and runs no replay.
- The workflow filter and the command read the same rule, so a local run, a job run and the workflow agree.
- A changed test with no source change gets no replay: a test-only fix proves nothing on base.

## Rejected alternatives
- Count prompts as code: a test of a prompt reads its text, which is a value test (#6060).
- Keep the scope only in the workflow filter: a local or job run of `devops ci fail-to-pass` would still ask a prompt fix for a test.
