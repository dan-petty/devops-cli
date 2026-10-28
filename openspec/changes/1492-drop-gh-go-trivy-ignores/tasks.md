# Tasks

## 1. No ignore stays for the Go findings that the pinned gh fixes

- [x] 1.1 Write the tests `test_service_image_installs_a_gh_release_built_with_go_1_27_2_or_later` and `test_trivyignore_ignores_no_go_finding_that_the_pinned_gh_fixes` in `tests/test_service_image_gh.py`, and see the second test fail on the three ignores with `uv run devops ci test tests/test_service_image_gh.py`
- [x] 1.2 Delete CVE-2026-78667, CVE-2026-97031, CVE-2026-78669 and their reason from `.trivyignore`; verify with `uv run devops ci test tests/test_service_image_gh.py tests/test_architectural_invariants.py`
- [x] 1.3 Regenerate the documentation; no command, option or message changes, so nothing changes; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
