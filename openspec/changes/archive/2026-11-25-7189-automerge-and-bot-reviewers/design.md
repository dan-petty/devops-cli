# Design

## Decisions

- Centralize reviewer filtering in `missing_pull_reviewers` (`src/devops_cli/github/client.py`), comparing normalized lowercase logins against `author` and existing `requested_reviewers` so callers never duplicate deduplication or author-exclusion logic and never trigger GitHub HTTP 422 on self-review requests.
- Parse `author` (`user.login`) and `requested_reviewers` directly on `CreatedPull` (`src/devops_cli/github/client.py`) and reuse `_extract_field_tuple` across `OpenPullRequest`, `PullStatus`, and `CreatedPull`.
- Pass `reviewers=(RepoRef(repo).owner,)` explicitly from automated roadmap callers (`roadmap/open_row.py`, `roadmap/stage/stage.py`, `roadmap/implement/implement_phases.py`, `commands/roadmap_step_open.py`) while keeping `OpenRequest.reviewers: Sequence[str] = ()` as the default so sweep recovery and existing direct unit calls preserve request budgets.
- Declare `template-pull-reviewers` in `github/onboard/routes.py` under `RouteOwner.TEMPLATE_PULL` (`Row 9`) so `RouteWriter` governs reviewer requests under `--plan` and `--confirm`, and request `ctx.options.repo.owner` when `pull` has a non-owner author and lacks the owner in `requested_reviewers`.
- Keep `.github/workflows/release.yml` using the already-minted Release App token (`steps.app.outputs.token`, `permission-pull-requests: write`) to call `gh api "repos/$REPOSITORY/pulls/$number/requested_reviewers"` only when `.user.login != dan-petty` and `dan-petty` is absent from `.requested_reviewers`.
- Remove `"automerge": false` from the `seaweedfs` rule in `.github/renovate.json` while keeping `dependencyDashboardApproval: true` so approved updates merge once all checks pass.

## Rejected alternatives

- Relying solely on `.github/CODEOWNERS`: GitHub Free ignores `CODEOWNERS` on private repositories (`src/devops_cli/github/onboard/settings_rows.py`), and `CODEOWNERS` does not cover release-please or roadmap bot PRs on private repos unless explicit reviewer requests are sent.
- Requesting `dan-petty` without checking `.user.login` or `created.author`: GitHub returns HTTP 422 when requesting a review from the PR author (`tests/support/github_repository.py`), which breaks runs where the owner opens the draft.
- Writing a Python test reading `.github/renovate.json`: blocked by `tests/gate/tree_checks/config_values.py:303` (`check_no_new_test_reads_a_committed_manifest_or_config_file`); config validity is verified by `renovate-config-validator --strict --no-global .github/renovate.json` instead.
- Adding `repeat=` to `other(...)` calls inside `stage_requests` (`src/devops_cli/roadmap/request_plan.py`): rejected at line 763 because `stage_requests`'s local `other` helper binds `repeat=each_item` automatically.
