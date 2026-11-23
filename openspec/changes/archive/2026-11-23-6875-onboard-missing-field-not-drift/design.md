# Design

## Decisions
1. **One rule in the model.** `held_differences(desired, live)` in `src/devops_cli/github/onboard/model.py` gives the differences of the top-level keys of `desired` that `live` holds, and the keys that `live` does not hold. Rows 2 and 10 call it in place of `differences`. Reason: the fault is one rule (a missing key is unknown), and both rows read a reply that GitHub cuts by permission.
2. **Top-level keys only.** A key inside a nested value, such as a parameter of a rule, still compares with `differences`. Reason: GitHub documents the cut for top-level fields only (the merge settings, `bypass_actors`). A missing nested key is a real difference of shape.
3. **Unknown is not readable, never pending.** A row with unknown keys and no other difference is `not readable`. The reason names the keys, and a person step names the permission and the command `devops repos onboard <repo> --plan --only <row>`, which reads the row with the login of a person. A row with other differences writes them and keeps the reason and the step. Reason: `not readable` already counts as its own state in the drift gauge and fails the plan (`_FAILING_STATES`), so the check never reads as clean.
4. **The permission in the person step.** Row 2 names Contents write and the document "Get a repository". Row 10 names write access to the ruleset (Administration write for an App) and the document "Get a repository ruleset".
5. **No change of the read set.** `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` gets no permission: only a write permission gives these fields, and the drift Job must change nothing (#6783). Its comment names the two fields that it cannot read.
6. **Row 3 stays as it is.** Its reads give the same changes for the read token and for the login of the owner (Feasibility), and no document names a field that its endpoints leave out.

## Rejected alternatives
- **Add Contents write and Administration write to the read set.** Rejected: the drift Job is read-only by design (`service.github_app.read_only`, #6783), and the brief of #6875 allows only a read permission. "Permissions required for GitHub Apps" lists `GET /repos/{owner}/{repo}` under Metadata read and gives the merge settings only with `contents:write`.
- **Drop the merge keys from the nightly `--only` set, or treat them as `present`.** Rejected: the check would then say clean for a setting that it never read, which hides real drift. `drift.py` counts `not readable` as its own state for this case.
- **Change `differences` so that a missing key at any depth is unknown.** Rejected: rows 3, 5 and 8 and the list match of rulesets read a missing nested key as a real difference, for example a rule of the baseline that the live ruleset lacks (`_list_matches` in `model.py`).
- **Read the merge settings with GraphQL.** Rejected: no document says that a read token gets them there, and a second read path for one row adds code for an unverified premise.
