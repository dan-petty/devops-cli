# Proposal

## Why

Issue #2569: `devops gh api` masks a token in a JSON reply together with the closing quote of the string, so the output is not valid JSON.

- The reply of `GET repos/<owner>/<repo>/contents/<path>` for a private repository has a `download_url` with a `token=` query parameter. The mask rewrites `...?token=<value>","type":"file"` to `...?token=<masked-token>,"type":"file"`. The quote that closes the string is gone, and `json.load` fails with `Expecting ',' delimiter`.
- The rules for `token`, `auth_token`, `password`, `passwd`, `pwd`, `client_secret` and `aws_secret_access_key` in `src/devops_cli/security/sanitizer.py` allow a quote mark before and after the value, and each of the two is optional alone. A value with no opening quote mark still takes a closing one. The replacement is a literal with no quote mark, so the closing quote mark of the enclosing string is lost. A value inside a string always ends at the closing quote of the string.
- `devops gh api` prints `mask_secrets(res.stdout)`. Any other text that holds a JSON string with such a secret breaks in the same way.

## What Changes

- A closing quote mark belongs to the match only when a quote mark of the same kind opened the value. A value with no opening quote mark ends before the quote mark that follows it, and that quote mark stays. A value in a pair of quote marks is masked with both marks, as before.
- The change fixes the four rules that share the defect: `password|passwd|pwd`, `token|auth_token`, `aws_secret_access_key` and `client_secret`. The other rules already pair their quote marks, or take no quote mark.
- One private helper in `sanitizer.py`, `_quoted`, writes the pair of quote marks once. The four rules use it. It replaces four hand-written pairs of `["']?`.
- The output of `redact_text`, `mask_secrets` and so of `devops gh api` is a result that a consumer sees. So the change carries a spec delta. It adds two requirements to the capability `secret-masking`: a closing quote mark stays when no quote mark opened the value, and a value in a pair of quote marks is masked with the pair.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: a closing quote mark that no opening quote mark of the value matched stays in the masked text.

## Impact

- `src/devops_cli/security/sanitizer.py`.
- `tests/security/test_secret_redaction.py`, `tests/security/test_redaction_properties.py` and `tests/commands/test_gh_cmd.py`.
- No command, option or message changes, so no generated documentation changes.

## Feasibility

- On `origin/main` at `5a4364c3`, `redact_text(json.dumps({"download_url": "https://example.com/o/r/f.txt?token=AGJ4EXAMPLE1234567890", "type": "file"}))` returned `...?token=<masked-token>, "type": "file"}`. `json.loads` of that text raised `JSONDecodeError: Expecting ',' delimiter`. The premise of the issue holds. A private repository is not needed: `devops gh api` passes the stdout of `gh` through `mask_secrets` (`src/devops_cli/commands/gh.py`, `api_cmd`), so a faked reply shows the same output.
- The cause is not the character class that the issue names. The value class `[^\s"',;]` already stops at a quote mark. The cause is the trailing `["']?` after the value: it matches a quote mark that no opening quote mark matched. The issue asks for a fix of "the pattern for a query-string token". The same trailing `["']?` is in the rules for `password|passwd|pwd`, `aws_secret_access_key` and `client_secret`, and the same run shows the same broken JSON for each of them. This answers the two open questions of the refine step.
- The rules for `api_key` and its kin pair their quote marks (`["'][...]["']` or no quote mark), and their run gave valid JSON, so they stay as they are.
- A conditional group of the `re` module in CPython 3.14.10, `(?P<quote>["'])?` followed by `(?(quote)(?P=quote)?)`, matches the closing quote mark only when the group matched. A run of the fixed rules gives `...?token=<masked-token>","type":"file"}` for the reply above, and `json.loads` parses it. A value in quote marks, such as `token="AGJ4EXAMPLE1234567890" next`, still gives `token=<masked-token> next`.
- Issue #2471 (a rule must not cross a line break) is closed and its fix is in the base. Pull request #3639 (issue #2613) and pull request #3676 (issue #2662) changed `sanitizer.py`, are merged and are in the base: the prose after a token colon stays unmasked and a user name with no password is masked. This change touches the quote groups of the rules that #3639 changed, so it starts from the merged text. No open pull request touches `sanitizer.py`: the files of the six open pull requests were listed on 2026-11-05.

## Existing Tool Considered

The alternatives check of the issue (2026-11-04) found no tool that fixes this. JSON masking libraries mask by key on a parsed object, and a log-redaction filter replaces whole matches in text, which is the behavior that takes the quote mark. The change uses the conditional group of the standard `re` module in the sanitizer that already exists. It adds one helper of three lines and builds nothing new. The change deletes the four hand-written pairs of `["']?` from the patterns.
