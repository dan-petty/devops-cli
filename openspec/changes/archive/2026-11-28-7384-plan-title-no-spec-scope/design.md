# Design

## Decisions
- Define `plan_title_prefix(has_spec_scope: bool) -> str` in `src/devops_cli/roadmap/pr_verdict.py` returning `"docs(spec): plan"` when `has_spec_scope` is `True` and `"docs: plan"` when `False`, plus pure `has_spec_scope_in_labels(declared)` returning `True` when `declared` is `None` or `"scope/spec" in declared`.
- Update `is_plan_title_prefix(title, *, has_spec_scope=True)` to match `plan_title_prefix(has_spec_scope)` strictly or legacy `"docs(openspec): plan"`, rejecting `"docs: plan"` when `has_spec_scope=True` and rejecting `"docs(spec): plan"` when `has_spec_scope=False`.
- Update `kind_of(..., *, has_spec_scope: bool = True)` in `implement_pull.py`; in `read_draft` and `stage_ready._settle`, inspect `.github/labels.yml` via `store.repository_file` (defaulting to `True` on `GitHubFileNotFoundError`).
- Extract `plan_check_title_problem` in `plan_check.py`, read `.github/labels.yml` on `base_ref` via `reads.get_file_at` (or base checkout when absent on test doubles, defaulting to `True` when missing), and add the `.github/labels.yml` read to `plan_check_requests`.
- Implement `stage_plan_title(issue, summary, *, has_spec_scope=True)` in `stage_change.py` using `plan_title_prefix`, have `staging_title` delegate to it, and accept `"docs"` in `_STAGING_TYPES` / `_PLAN_TITLE_RE`.

## Rejected alternatives
- Always accepting both `docs(spec): plan` and `docs: plan` regardless of repository scope: rejected because it weakens title validation in repositories that require `scope/spec`.
- Fetching repository labels inside `kind_of`: rejected because `kind_of` must remain pure without network I/O.
