# Design

## Decisions

- **Declarative route table in `constants.py` with segment matching**: `CONST_GH_API_PROTECTED_ROUTES` stores `(route_class, methods, pattern)` tuples where `{placeholder}` matches one path segment and `**` matches zero or more segments. Specific classes (`repository transfer`, `rulesets`, `secrets`) precede broader `settings` prefixes so the reported route class names the narrowest protected area.
- **Normalize endpoints before matching**: `normalize_gh_api_path` strips `scheme://host` if present, strips query parameters (`?...`) and fragments (`#...`), and strips leading/trailing slashes so `/repos/o/r/rulesets/1?force=true` and `repos/o/r/rulesets/1` resolve identically.
- **Reuse `parse_gh_api_args` for HTTP method resolution**: Because `gh api` turns `-f`, `-F`, and `--input` into `POST` even without `-X POST`, resolving args through `devops_cli.github.request_classifier.parse_gh_api_args` catches implicit writes before `run_gh` executes. If `parse_gh_api_args` fails to parse unknown flag syntax while an explicit method or field flag is present, the guard fails closed on the endpoint as a write.
- **Raise `GitHubApiAccessRefusedError(GitHubOperationError)` inside `api_cmd` after `--dry-run`**: `--dry-run` prints the planned request and sends nothing, so `dry_run` checks remain first. Live protected writes from agent callers raise a `DevOpsCLIError` reported through `new_typer()`'s exit seam with exit code 1 and a message naming the matched route class, pattern, and owner action.

## Rejected alternatives

- **Refuse all `POST`/`PATCH`/`PUT`/`DELETE` calls through `devops gh api`**: Rejected because agents routinely use `POST` on issue, pull request, label, and workflow dispatch routes during automated triage and CI workflows.
- **Block `--dry-run` on protected routes for agents**: Rejected because agents use `--dry-run` to preview the exact request command for the owner without mutating external state.

## Security

Agents share the owner's GitHub credentials in local and CI tool sessions (`core.caller.is_agent_caller()`). Without route-level enforcement, an agent invocation of `devops gh api` could modify repository merge/protection settings, alter or bypass rulesets, write or delete repository/environment/organization secrets, modify organization settings, or transfer repository ownership (`POST repos/{o}/{r}/transfer`). Enforcing `CONST_GH_API_PROTECTED_ROUTES` before subprocess dispatch keeps `GET` reads, `--dry-run` previews, and open collaboration routes (`issues`, `pulls`, `labels`, workflow `dispatches`) working while failing closed before any protected mutation reaches `gh` or `GitHubSession`. Documenting the guard in `docs/commands/gh.md` and `SECURITY.md` keeps operators informed of the enforced boundary and owner remediation path.
