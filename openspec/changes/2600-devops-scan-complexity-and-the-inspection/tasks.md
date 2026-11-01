# Tasks

## 1. Record the keep-port decision and verify the test

Reads: none. Changes: `src/devops_cli/core/code_metrics.py`.

- [ ] 1.1 The existing test in tests/test_code_metrics.py passes with all 12 parametrized samples, confirming the port matches Ruff's C901. No new test is needed because no behavior changes, and verify that `uv run devops ci test tests/test_code_metrics.py` fails on the base
- [ ] 1.2 Add one line to the module docstring of src/devops_cli/core/code_metrics.py after the existing first paragraph: 'Decision #2600: kept as the single source. Ruff is a dev dependency with no structured complexity field in its JSON output.', and verify that `uv run devops ci test tests/test_code_metrics.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
