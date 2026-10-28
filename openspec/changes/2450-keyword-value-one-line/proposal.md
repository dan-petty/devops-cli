# Proposal

## Why

Issue #2450: a credential keyword at the end of a line masks the first word of the next line.

- `redact_text` in `src/devops_cli/security/sanitizer.py` masks the value after a credential keyword with `\b(?:token|bearer|secret|password|api_key)\s+([A-Za-z0-9_\-.]{10,})\b`. In Python, `\s` also matches a line break. Thus, when a line ends with a keyword, the first word of the next line becomes its value. `_looks_like_a_credential` takes a word with a dot, an underscore or a digit as a credential, and masks it.
- A terminal transcript shows the problem: a command line ends with a config key whose name ends in `api_key`, and the output line starts with that key. `devops roadmap intake` refused such a bug report, because the masked body seemed to hold a secret. The body held no secret.
- Six more keyword-to-value patterns of the same pattern set use `\s` between the keyword or its separator (`:` or `=`) and the value: `password`, `token`, `aws_secret_access_key`, `client_secret`, `api_key` with a separator, and the `secret_` prefix after a separator, `Bearer` or `token`. Each one takes the first word of the next line as the value. The `password` and `token` rules replace the full match, so they also delete the line break and join the two lines.

## What Changes

- Between a credential keyword or separator and its value, every keyword-to-value pattern of `_build_secret_patterns` uses `[^\S\r\n]` (whitespace that is not a line break) in place of `\s`. The data and code pattern sets come from this one function, so both sets change.
- A line break ends the match. A keyword and its value on one line are masked as before, also when a no-break space or a tab separates them.
- The output of `redact_text`, `mask_secrets` and every caller of them is a result that a consumer sees, so the change carries a spec delta: an ADDED requirement of the capability `secret-masking`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: a credential keyword and its value sit on one line.

## Impact

- `src/devops_cli/security/sanitizer.py`.
- `tests/test_consolidation_security_sanitizer.py`.

## Feasibility

- On `origin/main` at `95eb8b68`, `redact_text("devops config set ai.api_key\nai.example_setting is now set")` returned `"devops config set ai.api_key\n<masked-token> is now set"`, in data and code syntax, and the same for a CRLF line break.
- On the same tree, `redact_text("Enter password:\nauthenticated_ok for user")` returned `"Enter password=<masked-password> for user"`: the rule masked the second line's first word and deleted the line break. The `token`, `aws_secret_access_key`, `client_secret`, `api_key` and `secret_` rules also masked the first word of the next line.
- The Python 3.14 `re` documentation says that `\s` in a `str` pattern matches the Unicode whitespace characters, which include `\n` and `\r`. `re.fullmatch(r"\s", "\xa0")` and `re.fullmatch(r"[^\S\r\n]", "\xa0")` both match, and `re.fullmatch(r"[^\S\r\n]", "\n")` does not.

## Existing Tool Considered

The fix changes one character class in existing patterns of Python's `re` module, from the standard library. The change builds nothing and deletes no internal code.
