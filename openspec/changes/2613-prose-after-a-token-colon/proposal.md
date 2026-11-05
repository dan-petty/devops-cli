# Proposal

## Why

Issue #2613: the output masking reads the prose `token: <word>` as a secret and rewrites the error text.

- Two rules of `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` have the defect. These are the `token|auth_token` rule and the `password|passwd|pwd` rule. Each rule takes a value of 8 or more characters after the keyword and a `:` or `=`. `_mask_literal` then replaces the whole match. It does not ask if the value is a credential or a word.
- A colon is also prose punctuation. buildx writes `failed to fetch oauth token: unexpected status from GET request to ...`. The rule makes it `failed to fetch oauth token=<masked-token> status from GET request to ...`. The printed error no longer says what failed. The same rule refused the first draft of the issue in `devops roadmap intake`, because the draft quoted the buildx error.
- The `password` rule has the same defect. `wrong password: authentication failed for the account` becomes `wrong password=<masked-password> failed for the account`.
- The project already has `_looks_like_a_credential`, which tells a word from a credential. The rule of the space-separated form `token <value>` uses it. The two colon-and-equals rules do not use it.

## What Changes

- The two rules name their separator as the group `sep`. `_mask_literal` leaves the match as written when three things hold. The separator is a colon, the value has no quote, and `_looks_like_a_credential` says the value reads as a word. A full stop at the end of the value is not part of the word, so `token: unexpected.` stays as written.
- An equals sign and a quote mark keep the value masked, whatever it looks like. `token=unexpected` and `password: "correcthorse"` are assignments. A password can be a plain word. So the change does not lower the masking of an assignment.
- The assignment operator `:=` and the form `token: =word` also keep the value masked. In both forms the value starts with an equals sign, and `_mask_literal` checks for it.
- The other rules of the pattern set do not change.
- The output of `redact_text`, `mask_secrets` and every caller of them is a result that a consumer sees. So the change carries a spec delta. It adds two requirements, one for the colon and one for an assignment. It also modifies the requirement "Syntax-aware secret masking" of the capability `secret-masking`.
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
- `_looks_like_a_credential` is in `sanitizer.py` already. A value is a credential when it has 24 or more characters. It is also a credential with a digit, a `_`, `-` or `.`, or a capital after its first character. `unexpected`, `authentication` and `Unauthorized` are words. The rule of the space-separated form uses the function today, so no new heuristic is built.
- The issue names two rules with one defect. No open or merged pull request touches `sanitizer.py`. The only open pull request is #3628, which changes the roadmap plan check.
- Two open issues change other parts of the module. Issue #2569 is about the closing quote of a `token=` value in JSON. Issue #2662 is about a user name in a URL. This change adds the `sep` group to the two regexes and a branch to `_mask_literal`. It leaves the value and quote groups as they are.

## Existing Tool Considered

The alternatives check of the issue (2026-11-04) found no tool. detect-secrets and gitleaks scan code and files and return findings. They do not rewrite a text at run time. So neither can replace the step that masks the output. The change uses the `_looks_like_a_credential` function of the module. It builds no new code beyond one branch in `_mask_literal` and a named group in two regexes. It deletes no internal code.
