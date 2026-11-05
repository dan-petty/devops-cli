# Design

## Context

See `proposal.md`. `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` makes the data and the code pattern sets. Two of its rules, `password|passwd|pwd` and `token|auth_token`, mask a value after a `:` or an `=` and call `_mask_literal` for the replacement.

## Goals / Non-Goals

**Goals:**

- A plain word after `token:` or `password:` in prose is printed as written.
- A credential is masked as before.

**Non-Goals:**

- The `api_key`, `client_secret` and `aws_secret_access_key` rules need 16 to 40 characters of the value, so they do not match a word of prose. They do not change.
- The closing quote of a `token=` value (#2569) and the user name of a URL (#2662) are other defects of the same module. Their issues own them.

## Decisions

### 1. Apply `_looks_like_a_credential` after a colon, in `_mask_literal`

Both rules call `_mask_literal`, so one branch covers both. The branch leaves the match as written when the separator is `:`, the value has no quote, and the value, with a full stop at its end removed, does not look like a credential.

- *Rationale*: the function exists, the last rule of the set uses it, and its tests cover title-case words and internal capitals (the `test_a_title_cased_word_is_not_a_credential` family).
- *Rationale for the full stop*: a sentence that ends with `token: unexpected.` would give the value `unexpected.`, and the function reads `.` as a separator. A full stop at the end of a word is punctuation.

### 2. Name the separator as the group `sep`

`_mask_literal` reads the separator from `match.group("sep")`. A named group of the regex is the form that the groups `quote` and `value` use already.

- *Rejected alternative*: read the separator from the text before the value. That depends on the text of the match and breaks when a rule changes its spacing.

### 3. The colon only; an equals sign and a quote mark keep the value masked

- *Rejected alternative*: apply the check to every separator, as the first design of the issue says. On `origin/main`, `redact_text("password=correcthorse")` returns `password=<masked-password>`, and `_looks_like_a_credential("correcthorse")` is false. With the check on `=`, the password would print in clear text. A password can be a lowercase word, and an equals sign or a quote mark states an assignment. The report of the issue is about a colon in prose, so the colon is the only separator that changes. A change that unmasks an assignment lowers the masking, which a security change must not do.

### 4. Reuse the heuristic, add no entropy rule

- *Rejected alternative*: an entropy score, as detect-secrets does. The alternatives check says that detect-secrets returns findings and cannot rewrite a text. A score also needs a threshold to tune, and the existing function already separates the words of the report from credentials, with tests.
- *Rejected alternative*: a larger minimum length in the regex. A short token with a digit would pass unmasked.

## Risks / Trade-offs

- [Risk] A line such as `password: correcthorsebattery` (a colon, no quote, 8 to 23 letters, no digit, no separator and no capital after the first character) is no longer masked. → Mitigation: a generated token or password nearly always has a digit, a capital or a separator, or runs to 24 characters, and `_looks_like_a_credential` is the rule that the space-separated form uses already. A value in quotes, or after an equals sign, is still masked. The trade-off is the one that the issue chose, and a person can reverse it.
- [Risk] The existing scenario "Default masking syntax" of `secret-masking` says that credentials are masked without condition. → Mitigation: its input is `password=settings.Hunter22`, an equals sign, and it still holds.
