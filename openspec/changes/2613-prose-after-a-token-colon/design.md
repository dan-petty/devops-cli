# Design

## Context

See `proposal.md`. `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` makes the data and the code pattern sets. Two of its rules, `password|passwd|pwd` and `token|auth_token`, mask a value after a `:` or an `=`. Both call `_mask_literal` for the replacement.

## Goals / Non-Goals

**Goals:**

- A plain word after `token:` or `password:` in prose is printed as written.
- A credential is masked as before.
- An assignment is masked as before.

**Non-Goals:**

- The `api_key`, `client_secret` and `aws_secret_access_key` rules need 16 to 40 characters of the value. They do not match a word of prose. They do not change.
- The closing quote of a `token=` value (#2569) and the user name of a URL (#2662) are other defects of the same module. Their issues own them.

## Decisions

### 1. Apply `_looks_like_a_credential` after a colon, in `_mask_literal`

Both rules call `_mask_literal`, so one branch covers both. The branch leaves the match as written when three things hold. The separator is `:`, the value has no quote, and the value does not look like a credential. The check removes a full stop at the end of the value first.

- *Rationale*: the function exists, the rule of the space-separated form uses it, and its tests cover title-case words and internal capitals (the `test_a_title_cased_word_is_not_a_credential` family).
- *Rationale for the full stop*: a sentence that ends with `token: unexpected.` gives the value `unexpected.`. The function reads `.` as a separator. A full stop at the end of a word is punctuation.

### 2. Name the separator as the group `sep`

`_mask_literal` reads the separator from `match.group("sep")`. The groups `quote` and `value` are named groups of the regex already.

- *Rejected alternative*: read the separator from the text before the value. That depends on the text of the match. It breaks when a rule changes its spacing.

### 3. The colon only; an equals sign and a quote mark keep the value masked

- *Rejected alternative*: apply the check to every separator, as the first design of the issue says. On `origin/main`, `redact_text("password=correcthorse")` returns `password=<masked-password>`. `_looks_like_a_credential("correcthorse")` is false. With the check on `=`, the password would print in clear text. A password can be a lowercase word. An equals sign or a quote mark states an assignment.
- The report of the issue is about a colon in prose, so the colon is the only separator that changes. A change that unmasks an assignment lowers the masking. A security change must not do that.

### 4. An equals sign after the colon keeps the value masked

The assignment operator `:=` of Make, Go and Pascal has an equals sign after the colon. So does the form `token: =word`. The regex gives the colon to `sep` and the rest to `value`, so the value starts with `=`. On `origin/main` these forms are masked. `_mask_literal` leaves a value that starts with `=` masked.

- *Rejected alternative*: the group `(?P<sep>:=|[:=])`. I ran it. `token:=abcdefg` has a 7-character value after `:=`, so the regex backtracks. It gives the `:` to `sep` and `=abcdefg` to `value`, and the branch prints the text as written. `token: =correcthorse` has a space, and the group does not match it. The check of the first character covers both forms.

### 5. Reuse the heuristic, add no entropy rule

- *Rejected alternative*: an entropy score, as detect-secrets does. The alternatives check says that detect-secrets returns findings and cannot rewrite a text. A score also needs a threshold to tune. The existing function already separates the words of the report from credentials, with tests.
- *Rejected alternative*: a larger minimum length in the regex. A short token with a digit would pass unmasked.

## Risks / Trade-offs

- [Risk] A line such as `password: correcthorsebattery` is no longer masked. It has a colon and no quote. The value has 8 to 23 letters, no digit, no separator and no capital after the first character.
  - Mitigation: a generated token or password nearly always has a digit, a capital or a separator, or runs to 24 characters. The rule of the space-separated form uses `_looks_like_a_credential` already. A value in quotes, or after an equals sign, is still masked.
  - The issue chose this trade-off, and a person can reverse it.
- [Risk] The scenario "Default masking syntax" of `secret-masking` said that credentials are masked without condition. That is no longer true for a plain word after a colon.
  - Mitigation: the delta modifies the requirement "Syntax-aware secret masking". The scenario now says that the exemption of code expressions does not apply in data syntax. The requirement names the colon exception. The example `password=settings.Hunter22` has an equals sign, and it still holds.
