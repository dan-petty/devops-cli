# Tasks

## 1. The request counter names the HTTP status (behavior)

- [x] 1.1 Write the failing tests. A session answer counts with its status, a 304 included. A gh command and an attempt with no answer count with status `none`.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`
- [x] 1.2 Count each paced session attempt after its answer. Count each paced gh attempt with status `none`. Remove the emit from `acquire`.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`
- [x] 1.3 Write the failing test for a paced attempt whose token is refused. It counts with status `none`. Then read the token inside that count.
  Verification: `uv run devops ci test tests/github/test_github_app_identity.py`

## 2. The pace lines log at DEBUG (behavior)

- [x] 2.1 Write the failing test. The mandatory pause and the quota window reset log at DEBUG. No record of them has level INFO.
  Verification: `uv run devops ci test tests/github/test_github_rate_limiter.py`
- [x] 2.2 Change the two `logger.info` calls to `logger.debug`. Correct the docstring of `_passed_reset_delay`.
  Verification: `uv run devops ci test tests/github/test_github_rate_limiter.py`

## 3. Documents (other)

- [x] 3.1 Regenerate the telemetry reference with `uv run devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Issue #3497 stays open for the slices that this change does not do.
- Refine slice: an unchanged item reads no comment.
- Cache slice: a last page under `per_page` is kept.
- Scoped intake slice: a page cap for scoped reads.
- stage_ready slice: a backoff after a failed check.
- Idle slice: a longer poll interval for a repository with no open work.
