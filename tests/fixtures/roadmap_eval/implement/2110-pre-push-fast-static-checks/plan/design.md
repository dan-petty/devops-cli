# Design

## Context

The pre-push hook `devops-ci-pre-push` ran `uv run devops ci`: every row of the check table, the test suite included, in the default fix mode. The `main` ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, and the `Static Analysis` and `Tests & Coverage` jobs of `.github/workflows/ci.yml` run `devops ci --check` with the same check table. The owner decided in #1752 that a push runs only the fast static checks, and that remote CI is the authoritative gate (ADR 0004).

## Decisions

- One hook of the `pre-push` stage runs `uv run devops ci --check --only lint,format,actionlint,zizmor`. The hook keeps its id `devops-ci-pre-push`. The installed `pre-push` script of pre-commit reads the configuration on each push, so a clone that installed the hooks before needs no new install.
- The hook runs in check-only mode. In the default fix mode, `ruff format` and `ruff check --fix` change the working tree during the push, and the pushed commit does not hold the change. In check-only mode, the hook reports the problem, and the author fixes it in a commit.
- The hook runs no test. The decision of #1752 names the four static checks only. The commit hooks run no test either (#2086), so the `Tests & Coverage` check of CI is the first run of the suite on a branch, unless the author runs `uv run devops ci` or `uv run devops ci test <paths>` by hand.
- AGENTS.md rule 5 names what runs before a push and before a merge, and leaves the names of the required checks to `docs/SDLC.md`, Phase 6, where the router sends the move from draft to merge. AGENTS.md is 6,450 characters with this rule. With the names in the rule, it is 6,505 characters, above the cap of 6,500 that `tests/test_agents_md_claims.py` holds.

## Rejected Alternatives

- Four hooks of the `pre-push` stage from `ruff-pre-commit`, an `actionlint` hook and a `zizmor` hook. The `ruff-pre-commit` revision is pinned apart from the locked `ruff`, and the `zizmor` row runs through `devops scan workflows`, which fails only on the findings that the repository blocks. One `devops ci --only` hook runs the commands of the `Static Analysis` job, so the hook and CI cannot disagree.
- The changed tests in the hook (#1752, question 2). The owner chose the four static checks, and a narrowed run on a loaded host is the cost that #2110 removes.
- The default fix mode. It changes files during a push, as the second decision says.

## Risks

- A push can now carry a failing test. The `Tests & Coverage` required check stops it before the merge, and `devops pr ready` comes only after the checks pass (AGENTS.md rule 6).
