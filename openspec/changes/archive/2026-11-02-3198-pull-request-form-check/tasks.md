# Tasks

## 1. Rules of the title and the body, in one module

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/roadmap/title_labels.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/pull_form.py` (new), `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_pull_form.py` (new), `tests/invariants/test_workflow_contracts.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_pull_form.py` for the scenarios of "The title has a type, a declared scope and a short summary", "The body ends with Closes and the Change line" and "The rules cut no text", and in `tests/invariants/test_workflow_contracts.py` for "The workflow and the module hold the same rule"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/invariants/test_workflow_contracts.py` fails on the base
- [x] 1.2 Add `pull_form.py` with `title_problems`, `body_problems`, `build_title`, `build_body` and `is_placeholder`, and their messages. Move `SUMMARY_MAX_CHARS` there and import it in `stage_change.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/invariants/test_workflow_contracts.py tests/roadmap/test_roadmap_stage_title.py`

## 2. `devops pr describe`

Kind: behavior. Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/pull_labels.py`, `src/devops_cli/roadmap/step_files.py`. Changes: `src/devops_cli/roadmap/pull_describe.py` (new), `src/devops_cli/commands/pr.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr_describe.py` (new), `tests/commands/test_pr_dry_run.py`, `tests/ai/mcp/test_mcp.py`.

- [x] 2.1 Write failing tests in `tests/commands/test_pr_describe.py` for the scenarios of "devops pr describe prints the title and the body", "devops pr describe refuses and prints nothing" and the dry run of describe, and add the command to `tests/commands/test_pr_dry_run.py` and the alias to the excluded list of `tests/ai/mcp/test_mcp.py`
  - Verification: `uv run devops ci test tests/commands/test_pr_describe.py tests/commands/test_pr_dry_run.py tests/ai/mcp/test_mcp.py` fails on the base
- [x] 2.2 Add `pull_describe.py`, the command `describe` with its options and help, and the MCP exposure `("pr", "describe")`
  - Verification: `uv run devops ci test tests/commands/test_pr_describe.py tests/commands/test_pr_dry_run.py tests/ai/mcp/test_mcp.py`

## 3. The check in `devops pr create`

Kind: behavior. Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/pull_labels.py`. Changes: `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr_form_check.py` (new), `tests/commands/test_pr_title_labels.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr_status.py`, `tests/commands/test_pr_dry_run.py`.

- [x] 3.1 Write failing tests in `tests/commands/test_pr_form_check.py` for the scenarios of "devops pr create refuses a pull request that breaks the form" and "A dry run checks the form without a request"; change `tests/commands/test_pr_title_labels.py` to give a body in the form and to expect the refusal of a scope with no label
  - Verification: `uv run devops ci test tests/commands/test_pr_form_check.py tests/commands/test_pr_title_labels.py` fails on the base
- [x] 3.2 Add the check to `create` (offline in a dry run), delete the warning `labels_scope_undeclared` and its use, and give the other `create` tests a form check that accepts their stand-in texts
  - Verification: `uv run devops ci test tests/commands/test_pr_form_check.py tests/commands/test_pr_title_labels.py tests/commands/test_pr_cmd.py tests/commands/test_pr_status.py tests/commands/test_pr_dry_run.py`

## 4. Document the command and the check

Kind: documents. Reads: `CONTRIBUTING.md`, `.github/pull_request_template.md`. Changes: `CONTRIBUTING.md`, `.github/pull_request_template.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/gh.md`, `docs/commands/pr.md`.

- [x] 4.1 Describe `devops pr describe` and the check of `devops pr create` in sections 4 and 5 of `CONTRIBUTING.md` and in the comment of the template, delete the sentence about the warning for a scope with no label, and regenerate the documentation with `devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`

## 5. Archive the change

Kind: other. Changes: `openspec/changes/3198-pull-request-form-check`, `openspec/specs/pull-request-form/spec.md`, `openspec/specs/pr-title-labels/spec.md`.

- [x] 5.1 Archive the change after every task is ticked
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- The stage and implement jobs call `build_title` and `build_body` instead of `staging_title`, `delivery_title`, `implement_pull_body` and the `textwrap.shorten` of `_why`, and send the refusal back to the model once, as they do for a plan. The implement body also changes its order to the text, `Closes`, `Change:`. This is a follow-up issue to file (the jobs, #3200 and the retry loop are the reason it is not in this pull request).
- `devops pr check-readiness` calls `body_problems` and reports its problems as blockers or advisories. It belongs to #2585, which owns the warning at 1,000 characters.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
