# Proposal

## Why

`devops pr create --dry-run` passed a title whose scope had no label, because the offline form check skipped the labels file. The real run then refused, and the dry run also said "Opened" for a run that opened nothing (#5178).

## What Changes

- In a dry run in the checkout of the target repository, `_form_checked` reads `.github/labels.yml` of the checkout and refuses a scope with no label as the real run does.
- A dry run with `--repo` names the labels read in its plan, because it cannot read the file of another repository.
- The dry run heading says "Would open a draft pull request into <base>" and states that the real run checks the title, the body and the labels.
- Add the two dry-run tests in `tests/commands/test_pr_dry_run.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: the dry run checks the scope against the checkout labels and says it would open.

## Impact

- Code: `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/pull_form.py`
- Tests: `tests/commands/test_pr_dry_run.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/commands/pr.py:1184:def _form_checked(` skips the labels when `offline`, and `:1343:` is the dry-run branch of `create_pr`.
- `src/devops_cli/github/labels.py:54:def load_label_specs(` reads the local file.
- `src/devops_cli/config/constants.py` holds `CONST_ROADMAP_LABELS_PATH`.
- `uv run pytest tests/commands/test_pr_dry_run.py` passes after the change.

## Existing Tool Considered

No open tool covers the dry run of this command. The change reads one local YAML file and reuses `title_problems`: about 1,500 tokens to build and 100 a quarter to keep.

## Dependencies

None.
