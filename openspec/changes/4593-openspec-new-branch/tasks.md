# Tasks

## 1. Name the branch of the checkout

Reads: `src/devops_cli/openspec/scaffold.py`, `src/devops_cli/commands/openspec.py`. Changes: the same files, `src/devops_cli/lang/en/messages.py`, and `tests/openspec/test_openspec_new.py`.

- [ ] 1.1 Read the branch of the checkout and take the slug of the same issue from it.
- [ ] 1.2 Print the branch of the checkout, or `HEAD detached`, and the suggestion.
- [ ] 1.3 Add the four tests.
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_new.py` passes
