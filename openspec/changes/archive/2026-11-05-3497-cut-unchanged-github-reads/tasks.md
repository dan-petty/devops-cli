# Tasks

## 1. The request counter names the HTTP status (behavior)

- [x] 1.1 Write the failing tests. A session answer counts with its status, a 304 included. A gh command and an attempt with no answer count with status `none`.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`
- [x] 1.2 Count each paced session attempt after its answer. Count each paced gh attempt with status `none`. Remove the emit from `acquire`.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`
- [x] 1.3 Write the failing test for a paced attempt whose token is refused. It counts with status `none`. Then read the token inside that count.
  Verification: `uv run devops ci test tests/github/test_github_app_identity.py`
- [x] 1.4 Write the test for a lost GET that the session sends again. Each attempt counts with its status.
  Verification: `uv run devops ci test tests/github/test_github_api_metrics.py`

## 2. The pace lines log at DEBUG (behavior)

- [x] 2.1 Write the failing test. The mandatory pause and the quota window reset log at DEBUG. No record of them has level INFO.
  Verification: `uv run devops ci test tests/github/test_github_rate_limiter.py`
- [x] 2.2 Change the two `logger.info` calls to `logger.debug`. Correct the docstring of `_passed_reset_delay`.
  Verification: `uv run devops ci test tests/github/test_github_rate_limiter.py`

## 3. Documents (other)

- [x] 3.1 Regenerate the telemetry reference with `uv run devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`
- [x] 3.2 Name the `status` label in the Service guide, `k8s/README.md`.
  Verification: `grep -n 'under its `method`, its `status`' k8s/README.md`

## Workflow follow-up

- This change closes #3497. The other criteria of #3497 moved to these issues:
- #3667: an unchanged refine item reads no comments, and the live sum query.
- #3670: scoped intake reads a bounded page count.
- #3671: stage_ready backs off after a failed check.
- #3672: an idle repository polls less often.
