# Task: mask_secrets masks every GitHub token prefix, ghu_, ghs_ and ghr_ included (#1398)

**Issue**: [#1398](https://github.com/dan-petty/devops-cli/issues/1398)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p1-high
**Scope**: type/security, scope/security, priority/p1-high

## Description

`mask_secrets` (`src/devops_cli/security/sanitizer.py`) masked `ghp_`, `gho_` and `github_pat_` tokens, but not the other three prefixes GitHub documents: `ghu_` (user-to-server), `ghs_` (server-to-server, such as a GitHub App installation token) and `ghr_` (refresh). #1124's review found the consequence: a `ghs_` token in a pre-receive hook's message would reach the release command's error output unmasked.

**Installation tokens changed shape.** GitHub App installation tokens, Actions' `GITHUB_TOKEN` among them, are now `ghs_APPID_JWT`: the prefix, the app ID, an underscore and a JWT whose three base64url segments are joined by dots and may contain `-` and `_`. They run to about 520 characters, and the length varies. Adding `ghu`, `ghs` and `ghr` to the old alternation would not have been enough. Its character class `[A-Za-z0-9_]` stops at the first dot, so the match would have covered the prefix, the app ID and the JWT header, and the payload and signature would still have been printed after `<masked-github-token>`.

**One pattern covers every prefix.** The first `_SECRET_PATTERNS` entry is now `(?<![A-Za-z0-9_<])(?:gh[pour]_[A-Za-z0-9_]{10,}|ghs_[A-Za-z0-9_.-]{36,}|github_pat_[A-Za-z0-9_]{20,})\b`, and it is still replaced with `<masked-github-token>`. Only `ghs_` admits `.` and `-`. The closing `\b` ends a match on a word character, so a full stop after a token is kept. A comment above the entry records how each minimum was chosen. No helper or extra guard was added.

**A prefix inside a longer word is left alone.** The lookbehind was `(?<![a-zA-Z0-9<])`, which let a `_` come before the prefix. A snake_case name with `_ghu_`, `_ghr_` or `_ghs_` and a long enough tail was masked: `def test_it_reads_ghu_login_of_the_user():` became `def test_it_reads_<masked-github-token>():`. `ghp_` and `gho_` had behaved this way since #116, and adding three prefixes would have spread it. Diffs pass through `mask_secrets` before review, so such names were corrupted. The lookbehind now excludes `_` as well, which is the word boundary TruffleHog's GitHub detector uses (`\b` before the prefix). A real token follows `=`, `:`, whitespace, a quote or `/`, not `_`. #116's assertion that `my_github_token_ghp_...` is masked contradicted this item's near-miss criterion, so it is removed from `test_mask_secrets_preserves_task_file_paths`. That test's `prefix-ghp_...` case, a token after `-`, is still masked.

**The diff path had its own GitHub pattern.** `src/devops_cli/ai/diff/difftastic.py` had a `_SECRET_PATTERNS` entry of its own, `(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}`, which `sanitize_diff_output` applied before calling `mask_secrets`. On a `ghs_APPID_JWT` token, it replaced the first 40 characters with `[REDACTED_SECRET]` and left the rest. With the prefix gone, `mask_secrets` no longer recognised a token, and the payload and signature were printed. The entry is deleted, and `sanitize_diff_output` now relies on `mask_secrets`, which it already called last. The rest of that list is unchanged. `get_structural_diff` and `sanitize_diff_output` have no caller outside `ai/diff/`, so this leak was latent, not live.

## How "documented minimum length" was read

- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github lists the six prefixes. The only length it states is 40 characters, for the legacy installation token. Removing the four-character `ghs_` prefix from 40 gives the 36-character minimum for `ghs_`. The minimum follows from that legacy length only. Identifiers that contain `_ghs_` are left alone by the lookbehind, not by the minimum.
- https://github.blog/changelog/2026-04-24-notice-about-upcoming-new-format-for-github-app-installation-tokens announces the `ghs_APPID_JWT` format for GitHub App installation server-to-server tokens, Actions' `GITHUB_TOKEN` included. It says the tokens will be about 520 characters and that the length will vary, so `ghs_` sets no upper bound.
- https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out reports the rollout complete. It warns that redaction rules matching only the legacy pattern miss the new tokens.
- GitHub states no length for `ghp_`, `gho_`, `ghu_` or `ghr_`. They keep the 10-character minimum that `ghp_` and `gho_` already had, so a shortened token in a log is still masked. `github_pat_` keeps its 20.

## Acceptance Criteria

- [x] `mask_secrets` masks every prefix GitHub documents (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`) in one pattern, each with the minimum length above. `test_every_github_token_prefix_is_masked_whole` masks a sample of each prefix, plus a `ghs_APPID_JWT` installation token, inside `remote: ... rejected`. It compares the whole line, which proves no part of a token is printed.
- [x] A parametrized test masks each sample inside surrounding text (`test_every_github_token_prefix_is_masked_whole`). `test_a_near_miss_github_token_is_left_alone` leaves seven near-misses unchanged: a short body for `ghu_`, `ghs_` and `github_pat_`, a prefix after a letter (`xghr_...`), and three snake_case names with `_ghu_`, `_ghr_` and `_ghs_` whose tails pass each minimum. The samples are built in code, so the test source holds no literal token. The `ghs_APPID_JWT` sample is built once, in `tests/github_token_samples.py`, which both test files import.
- [x] `sanitize_diff_output` masks a whole `ghs_APPID_JWT` token (`test_sanitize_diff_output_masks_a_whole_installation_token`), and `test_sanitize_diff_output_secrets` still passes.
- [x] Each new test's call phase stays under 1 s, and `uv run devops ci` passes. `changelog.d/1398.md` records the change under `### Security`, and `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.

## Red Then Green

Before the source change, these masking cases failed: `ghu_`, legacy `ghs_`, `ghr_` and the `ghs_APPID_JWT` installation token. The `ghp_`, `gho_` and `github_pat_` cases and all seven near-misses already passed. The diff test also failed: its output started with `[REDACTED_SECRET]`, followed by the rest of the token. With the new prefixes added but `_` still allowed before a prefix, the three snake_case near-misses failed, each masked from its prefix to the end of the name. After the change, every case passes.

## Deliverables

- [x] `src/devops_cli/security/sanitizer.py`: the first `_SECRET_PATTERNS` entry covers all six prefixes, with a comment explaining each minimum.
- [x] `src/devops_cli/ai/diff/difftastic.py`: the duplicate GitHub token pattern is removed.
- [x] `tests/test_consolidation_security_sanitizer.py` and `tests/test_difftastic.py`: the tests named above, and #116's `my_github_token_ghp_...` assertion removed.
- [x] `tests/github_token_samples.py`: the `ghs_APPID_JWT` sample both test files use.
- [x] `docs/agent/tasks/task-767-github-session-per-identity.md`: its follow-up on the missing prefixes now records that #1398 resolved it.
- [x] `changelog.d/1398.md`.

## Risks and Notes

- Because a `ghs_` match can contain dots, a file name made of a long `ghs_` token and an extension is masked together with its extension. A `ghp_` match stops before the dot.
- The other entries in `difftastic.py`'s `_SECRET_PATTERNS` (private keys, keyword assignments, `sk-` and `AKIA`) overlap `mask_secrets` as well. They are outside this item and unchanged.
- A token glued to a word by `_`, such as `my_github_token_ghp_...`, is no longer masked. That is the cost of leaving snake_case names alone, and TruffleHog's `\b((?:ghp|gho|ghu|ghs|ghr|github_pat)_...)` skips the same case.
- A token right after `<` is never masked, for any prefix, because `<` has been in the lookbehind since v0.2.18 (#116). `<ghs_...>`, as in a Markdown autolink or a hook message that wraps the value in angle brackets, is printed whole. The `sk-` patterns have the same `<`. Why `<` was added is not recorded in #116's task file or commit. This predates this change and is outside its criteria; it needs a follow-up issue, filed within the #1153 quota after finding out why `<` is there.
