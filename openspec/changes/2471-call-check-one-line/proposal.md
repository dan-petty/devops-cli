# Proposal

## Why

Issue #2471: the line after a credential decides whether the credential is masked.

- The `api_key` rule of `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` masks the value after `api_key`, `access_token`, `bearer_token` or `auth_token` and a separator. After an unquoted value, the rule has the call check `(?!\s*\()`, so that it does not mask a call such as `api_key=settings_mod.get_ai_api_key(st)`. In Python, `\s` also matches a line break. Thus, when the next line, or a line after blank lines, starts with `(`, the check stops the match, and the value stays in clear text.
- The requirement "A credential keyword and its value sit on one line" of the `secret-masking` spec takes the value only from the same line. #2450 changed the patterns between a keyword and its value, but kept this check as it was.
- The review of the #2450 fix also found three gaps in its tests:
  - No test puts a line break between a keyword and its separator. Each of the `password`, `token`, `aws_secret_access_key`, `client_secret` and `api_key` rules can go back to `\s` before the separator, and all tests still pass. The same is true for the `token` alternative of the `secret_` rule.
  - No test joins a one-line pair with a tab or a no-break space. If each `[^\S\r\n]` becomes `[ ]`, all tests still pass, but a no-break space after `password:` no longer joins the keyword and its value.
  - The one-line test does not compare the whole result with an expected text, as docs/TESTING.md tells. A change to the replacement text of a rule still passes it.

## What Changes

- The call check after an unquoted `api_key` value becomes `(?![^\S\r\n]*\()`. A `(` on the same line, also after a space or a tab, continues to stop the match. A line break ends the check, so the next line does not change the result.
- The tests give each keyword-to-value rule a pair with the line break between the keyword and its separator, and compare the one-line result of each pair with its whole expected text, with a space, a tab or a no-break space between the two parts. A property test shows that the line after a credential line never changes the result for that line.
- The output of `redact_text`, `mask_secrets` and every caller of them is a result that a consumer sees, so the change carries a spec delta for the capability `secret-masking`: a MODIFIED requirement for the whitespace between a keyword and its value, and an ADDED requirement for the text after a line break.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: a tab or a no-break space joins a keyword, its separator and its value, and a new requirement says that the text after a line break does not change the result for the line before it.

## Impact

- `src/devops_cli/security/sanitizer.py`.
- `tests/test_consolidation_security_sanitizer.py`.

## Feasibility

- On `origin/main` at `960e3573`, `redact_text("api_key: Zq8xW2mN4pL7vR9tK3yB6cJ1\n(rotated monthly)")` returned the input unchanged, in data and code syntax. With `rotated monthly` on the second line, it returned `api_key=<masked-api-key>\nrotated monthly`. `access_token=` with the same value and a blank line before `(next paragraph)` also came back unchanged.
- On the same tree, the rule with `(?![^\S\r\n]*\()` masked the three inputs above, and left `api_key=settings_mod.get_ai_api_key(st))` and `api_key = settings_mod.get_ai_api_key (st)` unchanged.
- On the same tree, the 136 tests of `tests/test_consolidation_security_sanitizer.py`, `tests/test_url_credential_masking.py` and `tests/test_review_syntax_masking.py` passed with each of these changes to `sanitizer.py`: one `[^\S\r\n]` before a separator back to `\s` (for each of the five rules), the `token` alternative of the `secret_` rule back to `\s+`, and each `[^\S\r\n]` changed to `[ ]`.
- The Python 3.14 `re` documentation says that `\s` in a `str` pattern matches the Unicode whitespace characters, which include `\n` and `\r`.

## Existing Tool Considered

The fix changes one character class in an existing pattern of Python's `re` module, from the standard library. The property test uses Hypothesis, which the test suite already uses. The change builds nothing and deletes no internal code.
