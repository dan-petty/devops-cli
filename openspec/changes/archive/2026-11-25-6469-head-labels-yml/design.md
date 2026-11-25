# Design

## Decisions
- Add `declared_labels_for_refs(store, *, ref, head)` in `src/devops_cli/roadmap/pull_labels.py` and call it from both `read_title_labels` and `declared_label_set`, catching only `GitHubFileNotFoundError` when a second ref exists and propagating YAML, schema, and API errors immediately.
- Add optional keyword `labels_source: str | None = None` to `title_problems` so one `form_title_scope` message renders checkout mode (`.github/labels.yml`), `--repo` only (`.github/labels.yml on <base>`), and `--repo` + `--head` (`.github/labels.yml on <base> or <head>`) without duplicating message strings.
- Pass `head=head if repo is not None else None` through `_form_checked`, `_finish_created_pr`, `_labels_recorded`, and `_plan_title_labels`, and share label request planning via `plan_pr_title_labels` in `src/devops_cli/github/pr_plans.py`.

## Rejected alternatives
- Reword the `--repo` refusal without reading `head`: refuses valid cross-repo pull requests that add a new scope label on their branch.
- Duplicate `form_title_scope` into separate message fields: creates drift between modes.
- Swallow all `GitHubOperationError` exceptions when reading `head`: hides invalid YAML or API failures.

## Security
No new trust boundary, secret, or permission scope. Only reads `.github/labels.yml` from user-specified `--base` and `--head` refs via the existing `RoadmapStore.repository_file` API and propagates non-not-found errors explicitly.
