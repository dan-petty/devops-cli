# Tasks

## 1. A key that the reply does not hold is not readable

Kind: behavior. Reads: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/drift.py`, `tests/support/github_repository.py`. Changes: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/settings_rows.py`, `tests/github/onboard/test_onboard_rows.py`.
Adds: `held_differences`, `DOC_GET_REPOSITORY`, `DOC_GET_RULESET`

- [ ] 1.1 Write the failing tests in `tests/github/onboard/test_onboard_rows.py`. `test_a_reply_without_the_merge_settings_makes_row_2_not_readable`: an onboarded repository whose reply holds none of the 8 merge keys gives row 2 `not readable`, no change, a reason that names each key, the person step of Contents write with the document "Get a repository", and no write. `test_a_reply_without_the_merge_settings_still_writes_a_known_difference`: the same reply with `has_issues: false` gives row 2 `pending` with the one change `has_issues: True` and the same reason. `test_a_ruleset_reply_without_bypass_actors_makes_row_10_not_readable`: a live ruleset with no `bypass_actors` gives row 10 `not readable`, a reason that names `bypass_actors`, and no write. `test_a_reply_with_the_merge_settings_of_the_baseline_is_present`: an onboarded repository gives row 2 `present`. The first three fail on the base, which gives `pending`
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [ ] 1.2 Add `held_differences(desired, live)` to `src/devops_cli/github/onboard/model.py`: the differences of the top-level keys of `desired` that `live` holds, and the keys that `live` does not hold. Add `DOC_GET_REPOSITORY` and `DOC_GET_RULESET`. In `src/devops_cli/github/onboard/settings_rows.py`, make `repository_row` and `ruleset_row` compare with `held_differences`: a row with unknown keys and no other difference is `not readable`, its reason names the keys, and its person step names the permission and the plan command of the row
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py tests/commands/test_repos_onboard.py` passes

## 2. State the rule and the permissions

Kind: other. Reads: `docs/repos/onboard.md`, `k8s/README.md`, `src/devops_cli/config/constants.py`. Changes: `docs/repos/onboard.md`, `k8s/README.md`, `src/devops_cli/config/constants.py`.

- [ ] 2.1 In the comment of `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS`, name the two fields that only a write permission gives: the merge settings (Contents write) and `bypass_actors` of a ruleset (Administration write)
  - Verification: `$ uv run devops ci --check --only lint` passes
- [ ] 2.2 In `docs/repos/onboard.md`, state the rule in the rows section and in the nightly Job section: rows 2 and 10 are `not readable` for the keys that the read token cannot read. In the alert table of `k8s/README.md`, name the cause in the row of `RepositorySettingsUnreadable`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
