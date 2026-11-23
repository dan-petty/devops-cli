# Proposal: #6875

## Why
Closes #6875. Row 2 (Repository) of `devops repos onboard` compares the `repository` body of the baseline with `GET /repos/<repo>` through `model.differences`, which counts a key that the reply does not hold as a difference. GitHub gives the merge settings only to a token with Contents write. The nightly drift Job (CronJob `repos-drift`, #6783) reads with an App installation token that asks for `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS`, so its reply holds none of the 8 merge keys of the baseline. On 2026-11-23 the Job reported row 2 of each repository as `pending` with each merge key, and `RepositorySettingsDrift` fired. The same plan with the login of the owner gives row 2 `present`. Row 10 (Ruleset) has the same fault: GitHub gives `bypass_actors` of a ruleset only to a token with write access to the ruleset, and the baseline holds `bypass_actors: []`.

## What Changes
- A top-level key of the baseline that the reply of GitHub does not hold is unknown, not a difference. Rows 2 and 10 compare only the keys that the reply holds, and they never give an unknown key as a change.
- A row with unknown keys and no other difference is `not readable`. Its reason names the unknown keys, and a person step names the permission that GitHub needs and the plan command that reads the row with the login of a person. A row with unknown keys and other differences stays `pending` or `applied`, with the same reason and step.
- `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` does not change: no read permission gives these fields (Feasibility).
- Row 3 does not change: it has no such fault (Feasibility).
- The state of a row and its person step are observable output of a devops command, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities
- `repos-onboard`: ADDED requirement "A key that the reply does not hold is not readable".

## Impact
- The drift Job reports row 2 of each repository, and row 10 of each repository with a ruleset, as `not readable`, not as `pending`. `RepositorySettingsDrift` no longer fires for these keys, and `RepositorySettingsUnreadable` fires instead, because the read token cannot read them.
- A person who runs the plan with the own login sees no change of output: that token gets each key.
- `docs/repos/onboard.md` and the alert table of `k8s/README.md` state the rule and the permissions.

## Feasibility
- GitHub REST documentation, "Get a repository" (`docs.github.com/en/rest/repos/repos#get-a-repository`, read 2026-11-23): "To view merge-related settings, you must have the contents:read and contents:write permissions."
- GitHub REST documentation, "Get a repository ruleset" (`docs.github.com/en/rest/repos/rules#get-a-repository-ruleset`, read 2026-11-23): "the bypass_actors property is only returned if the user making the API request has write access to the ruleset." "Permissions required for GitHub Apps" lists `PUT /repos/{owner}/{repo}/rulesets/{ruleset_id}` under Administration write.
- The same page lists `GET /repos/{owner}/{repo}` and `GET /repos/{owner}/{repo}/rulesets/{ruleset_id}` under Metadata read only. So no read permission gives the merge settings or `bypass_actors`, and the read set gets no new permission.
- Live output, Loki stream of pod `repos-drift-manual-6784-4fw56` (2026-11-23): row 2 of dan-petty/devops-cli `pending` with the 8 keys `allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`, `squash_merge_commit_title`, `squash_merge_commit_message`, `allow_auto_merge`, `allow_update_branch`, `delete_branch_on_merge`. `devops repos onboard dan-petty/devops-cli --plan --only 2,3,10` with the login of the owner on origin/main `0237614bb`: row 2 `present`.
- Row 3: the same plan with the login of the owner gives the same 4 row 3 changes as the Job, and the documentation of its 5 endpoints names no field that GitHub leaves out of a reply; a token without access gets 403 or 404, which the row already handles. Row 10 of devops-cli is `pending` for both tokens on a real difference (`conditions` and one more rule), which this change does not touch.

## Existing Tool Considered
- No tool compares a desired GitHub setting with a reply that hides fields by permission. The project owns the comparison (`model.differences`, ADR 0035), so the fix goes there.
- Build cost: about 30 lines of code and 3 tests; about 40k tokens and 1 hour.
- The change deletes no internal code.
