# Tasks

## 1. The request counter names the HTTP status (behavior)

- [x] 1.1 Write the failing tests: a session answer counts with its status, a 304 included; a gh command counts with status `none`; an attempt that gets no answer counts with status `none`.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`
- [x] 1.2 Count each paced attempt in the session after its answer, and each paced gh attempt with status `none`, and remove the emit from `acquire`.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`
- [x] 1.3 Write the failing test that a paced attempt whose token is refused counts with status `none`, then read the token inside that count.
  Verification: `uv run devops ci test tests/github/test_github_app_identity.py`

## 2. The pace lines log at DEBUG (behavior)

- [x] 2.1 Write the failing test that the mandatory pause and the quota window reset log at DEBUG, and that no record of them has level INFO.
  Verification: `uv run devops ci test tests/github/test_github_rate_limiter.py`
- [x] 2.2 Change the two `logger.info` calls to `logger.debug` and correct the docstring of `_passed_reset_delay`.
  Verification: `uv run devops ci test tests/github/test_github_rate_limiter.py`

## 3. Documents (other)

- [x] 3.1 Regenerate the telemetry reference with `uv run devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Follow-up issue #3497 stays open for the slices this change does not do: the refine slice (a comment read for an unchanged item), the cache slice (a last page under `per_page`), the scoped intake page cap, the stage_ready backoff, and the idle poll interval.
