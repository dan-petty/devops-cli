# Proposal

## Why

Issue #1916: the review guards in `.devops/review.md` have no reader. #1881 moved them out of `AGENTS.md`, but no review stage gives their text to a model, and Copilot code review does not read the file. A rule that nothing reads checks nothing.

## What Changes

- `.devops/review.md` is deleted, with `nearest_review_conventions`, `CONST_REVIEW_CONVENTIONS_FILE`, the route of `devops ai agents` to the file, and its entry in the prompt class of the documentation check.
- `devops review corpus generate` copies only the source's conventions file, and a pull request checkout takes only `AGENTS.md` and its peers from the base. Neither copies `.devops/review.md`, which no stage reads.
- `ai/tasks/review.md` and `docs/SELF_IMPROVEMENT.md` no longer name the file as a source of rules.
- The commands write different files, so the change carries a spec delta: the new capability `review-conventions`.
- `DEFAULT_REVIEW_CONVENTIONS_MAX_CHARS`, which the issue names, is already gone from `main`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `review-conventions`: which project files a review copies with the code it reviews, and which file a generated `AGENTS.md` routes a review to.

## Impact

- `.devops/review.md` (deleted), `src/devops_cli/ai/review/review_environment.py`, `src/devops_cli/ai/review/defects.py`, `src/devops_cli/ai/review/runner.py`, `src/devops_cli/ai/review/profile.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/tasks/review.md`.
- `docs/SELF_IMPROVEMENT.md`.
- Tests: `test_review_project_conventions.py` (its guard snapshot is deleted), `test_review_defects.py`, `test_review_scope.py`, `test_batch_2_review_defects.py`, `test_git_operations.py`, `test_review_profile.py`, `test_agents_md_claims.py`.

## Feasibility

- On `origin/main` 46958d4b, `nearest_review_conventions` had one caller, `devops review corpus generate`, which copied the file into the corpus. `_materialize_pr_head` copied it from the pull request base. No prompt builder of the review read the file, and `ReviewProfiler.set_conventions` had no caller in `src`.
- The group analysis stage explains findings that tools admitted. Its G10 check refuses a finding id outside the admitted set (`review/analysis.py`), so a guard against a finding that a model makes up has no job there (ADR 0005).
- GitHub's page "Adding repository custom instructions for GitHub Copilot" (read 2026-10-29): Copilot code review reads `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` and agent instructions such as `AGENTS.md` from the head branch. It does not read `.devops/review.md`.
- The three new tests failed on `origin/main`: the corpus held `.devops/review.md`, the pull request checkout held it, and a generated `AGENTS.md` routed to it.

## Existing Tool Considered

For an LLM reviewer, the open tool is Copilot code review's own path-specific instructions, a `.github/instructions/*.instructions.md` file with `excludeAgent: "cloud-agent"`. This change does not move the guards there, because Copilot reviews run only when a person asks (AGENTS.md rule 6). For a scanner's false positive, the reviewed mechanism stays `.devops/review.toml`. The change builds nothing. It deletes `.devops/review.md`, `nearest_review_conventions`, `_read_review_conventions_file`, `CONST_REVIEW_CONVENTIONS_FILE`, the `review_conventions` parameter of `generate_corpus`, and the guard tests and their snapshot.
