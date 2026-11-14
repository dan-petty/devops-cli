# Tasks

## 1. Check an edited title

Reads: `src/devops_cli/commands/pr.py`. Changes: the same file and `tests/commands/test_pr_update.py`.

- [ ] 1.1 Add `_edit_title_checked` and call it when `--title` is given.
- [ ] 1.2 Add the two refusal tests.
  - Verification: `$ uv run devops ci test tests/commands/test_pr_update.py` passes
