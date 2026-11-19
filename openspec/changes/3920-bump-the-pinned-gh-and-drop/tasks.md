# Tasks

## 1. Raise the gh floor to the pinned v2.105.0

Kind: other. Reads: `Dockerfile`, `src/devops_cli/roadmap/runner_tools.py`, `tests/invariants/test_service_image.py`, `.trivyignore`. Changes: `tests/invariants/test_service_image.py`.

- [ ] 1.1 Set `GH_FIRST_SAFE_VERSION` in `tests/invariants/test_service_image.py` to `Version("2.105.0")` and rewrite the comment above it: gh v2.105.0 is the first cli/cli release whose go.mod holds golang.org/x/net 0.62.0, which ends CVE-2026-78661 (#3920), and it also keeps the Go 1.27.2 bound of #1492. Extend the docstring of `test_service_image_installs_a_gh_release_built_with_go_1_27_2_or_later` to name #3920. The Dockerfile pin and `GH_VERSION` stay at 2.105.0
  - Verification: `$ uv run devops ci test tests/invariants/test_service_image.py` passes

## 2. Add CVE-2026-78661 to the findings that the pin fixes

Kind: other. Reads: `tests/invariants/test_service_image.py`, `.trivyignore`, `.trivyignore-tofu`. Changes: `tests/invariants/test_service_image.py`.

- [ ] 2.1 Add `CVE-2026-78661` to `GH_GO_FINDINGS_FIXED_IN_THE_PIN` in `tests/invariants/test_service_image.py` and rewrite the comment above it: the three findings of gh v2.102.0 are fixed by v2.102.1 (#1492), and CVE-2026-78661 in golang.org/x/net 0.60.0 is fixed by v2.105.0 with 0.62.0 (#3920). Extend the docstring of `test_trivyignore_ignores_no_go_finding_that_the_pinned_gh_fixes` to name #3920. Leave the entry in `.trivyignore-tofu`, which the Service image scan does not read
  - Verification: `$ uv run devops ci test tests/invariants/test_service_image.py` passes

## Criteria

- Group 1: The pinned release is the first cli/cli release whose `go.mod` has `golang.org/x/net` 0.62.0 or newer (read with `devops gh api repos/cli/cli/contents/go.mod?ref=<tag>`).
- Group 1: The `Dockerfile` has the new version, the SHA-256 checksum of both archives (amd64 and arm64) and the path in the install step. `GH_VERSION` in `src/devops_cli/roadmap/runner_tools.py` and the floor in `tests/invariants/test_service_image.py` match the pin.
- Group 2: The entry `CVE-2026-78661` and its reason are removed from `.trivyignore`.
- Group 2: `Runner Image` and `Service Image` pass on a pull request that changes no image.
- Pending person: This work is done before 2026-11-21, the day the ignore ends. If cli/cli has no release by then, a person decides whether to move the date., Only a person owns the date: the ignore ends on 2026-11-21 and the removal waits on the promtool and OpenTofu bumps in #6365 and #5866 through #6389, so a person decides any move of the date.
