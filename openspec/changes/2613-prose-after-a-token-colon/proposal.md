# Proposal

## Why

Issue #2613: the output masking reads the prose `token: <word>` as a secret and rewrites the error text.

- The `token|auth_token` rule and the `password|passwd|pwd` rule of `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` take a value of 8 or more characters after the keyword and a `:` or `=`. `_mask_literal` then replaces the whole match, and it does not ask if the value is a credential or a word.
- A colon is also prose punctuation. buildx writes `failed to fetch oauth token: unexpected status from GET request to ...`, and the rule makes it `failed to fetch oauth token=<masked-token> status from GET request to ...`. The printed error no longer says what failed. The same rule refused the first draft of the issue in `devops roadmap intake`, because the draft quoted the buildx error.
- The `password` rule has the same defect: `wrong password: authentication failed for the account` becomes `wrong password=<masked-password> failed for the account`.
- The project already has `_looks_like_a_credential`, which tells a word from a credential. The last rule of the pattern set uses it for the space-separated form `token <value>`. The two colon-and-equals rules do not use it.

## What Changes

- The two rules name their separator as the group `sep`. `_mask_literal` leaves the match as written when the separator is a colon, the value has no quote, and `_looks_like_a_credential` says the value reads as a word. A full stop at the end of the value is not part of the word, so `token: unexpected.` stays as written.
- An equals sign and a quote mark keep the value masked, whatever it looks like. `token=unexpected` and `password: "correcthorse"` are assignments, and a password can be a plain word. So the change does not lower the masking of an assignment.
- The other rules of the pattern set do not change.
- The output of `redact_text`, `mask_secrets` and every caller of them is a result that a consumer sees, so the change carries a spec delta: an ADDED requirement of the capability `secret-masking`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: a plain word after a credential keyword and a colon is left as written.

## Impact

- `src/devops_cli/security/sanitizer.py`.
- `tests/security/test_secret_redaction.py`.

## Feasibility

- On `origin/main` at `66a8a63e`, `redact_text("failed to fetch oauth token: unexpected status from GET request to https://ghcr.io/v2/x: 403 Forbidden")` returned `failed to fetch oauth token=<masked-token> status from GET request to https://ghcr.io/v2/x: 403 Forbidden`, in data and in code syntax. `redact_text("wrong password: authentication failed for the account")` returned `wrong password=<masked-password> failed for the account`. The premise of the issue holds.
- `tests/k8s/test_image_pins.py` holds the recorded buildx error `failed to fetch anonymous token: unexpected status from GET request to https://ghcr.io/token?...: 403 Forbidden` of `devops k8s image-pins`. After the change, `redact_text` returns this text as it is.
- `_looks_like_a_credential` is in `sanitizer.py` already. A value is a credential when it has 24 or more characters, a digit, a `_`, `-` or `.`, or a capital after its first character. `unexpected`, `authentication` and `Unauthorized` are words. The `token`, `bearer`, `secret`, `password` and `api_key` rule that takes the space-separated form uses it today, so no new heuristic is built.
- The issue names two rules with one defect, and the open and merged pull requests do not touch `sanitizer.py`: the only open pull request is #3628, which changes the roadmap plan check. The open issues #2569 (the closing quote of a `token=` value in JSON) and #2662 (a user name in a URL) change other parts of the module. This change adds the `sep` group to the two regexes and a branch to `_mask_literal`, and it leaves the value and quote groups as they are.

## Existing Tool Considered

The alternatives check of the issue (2026-11-04) found no tool. detect-secrets and gitleaks scan code and files and return findings, and they do not rewrite a text at run time, so neither can replace the step that masks the output. The change uses the `_looks_like_a_credential` function of the module and builds no new code beyond one branch in `_mask_literal` and a named group in two regexes. It deletes no internal code.
