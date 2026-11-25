# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests covering head-only scope labels, base-only scope labels with `--head`, ref-qualified scope refusal messages across `--repo`+`--head`, `--repo` without `--head`, checkout mode, post-create labeling from `--head`, malformed head `labels.yml`, and dry-run plans
  - Verification: `$ .venv/bin/pytest -n 0 tests/commands/test_pr_form_check.py tests/commands/test_pr_title_labels.py tests/roadmap/test_roadmap_pull_form.py`
- [x] 1.2 Implement `declared_labels_for_refs`, `labels_source` in `title_problems`, `plan_pr_title_labels`, and pass `head` across `_form_checked`, `_labels_recorded`, and `_plan_title_labels`
  - Verification: `$ .venv/bin/pytest -n 0 tests/commands/test_pr_form_check.py tests/commands/test_pr_title_labels.py tests/commands/test_pr_other_repository.py tests/commands/test_pr_dry_run.py tests/commands/test_pr_cmd.py tests/commands/test_pr_describe.py tests/roadmap/test_roadmap_pull_form.py`

## 2. Documents

- [x] 2.1 Update `pull-request-form` spec and OpenSpec artifacts
  - Verification: `$ .venv/bin/devops openspec check`
