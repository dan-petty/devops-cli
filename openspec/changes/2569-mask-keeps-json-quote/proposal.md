# Proposal

## Why

Issue #2569: `devops gh api` masks a token in a JSON reply together with the quote mark that closes the string. The printed text is then not valid JSON.

- The reply of `GET repos/<owner>/<repo>/contents/<path>` for a private repository has a `download_url` with a `token=` query parameter. The mask rewrites `...?token=<value>","type":"file"` to `...?token=<masked-token>,"type":"file"`. The quote mark that closes the string is gone. `json.load` fails with `Expecting ',' delimiter`.
- The rules for `token`, `auth_token`, `password`, `passwd`, `pwd`, `client_secret` and `aws_secret_access_key` are in `src/devops_cli/security/sanitizer.py`. Each rule allows a quote mark before the value and one after it. The two marks are optional alone, so a value with no opening quote mark still takes a closing one. The replacement is a literal with no quote mark, so the quote mark of the enclosing string is lost.
- A second defect hides behind the first. The value class of the `token` and `password` rules holds the backslash. JSON text writes a quote mark inside a string as a backslash and the mark. A value before such a pair lost its backslash to the mask, and the quote mark stayed with no escape.
- Before this change, the trailing quote mark of the old rule took the whole pair, so that text stayed valid JSON by chance. A fix of the closing quote mark alone makes that text invalid. So the value must also stop before an escaped quote mark.
- `devops gh api` prints `mask_secrets(res.stdout)`. Any other text with a JSON string that holds such a secret breaks in the same way.

## What Changes

- A closing quote mark belongs to the match only when a quote mark of the same kind opened the value. A value with no opening quote mark ends before the quote mark that follows it, and that quote mark stays. A value in a pair of quote marks is masked with both marks, as before.
- A value also ends before a backslash that starts an escaped quote mark, `\"` or `\'`. A double backslash is one character of the value. So the mask never splits a JSON escape.
- The change fixes the four rules that share the defect of the quote mark: `password|passwd|pwd`, `token|auth_token`, `aws_secret_access_key` and `client_secret`. The other rules pair their quote marks, or take none.
- The value classes of `aws_secret_access_key` and `client_secret` hold no backslash. So only the rules for `password` and `token` change their value class.
- One private helper, `_quoted`, writes the pair of quote marks once. One constant, `_VALUE_CHAR`, writes one character of a value. The rules use both, in place of four hand-written pairs of `["']?`.
- The output of `redact_text`, `mask_secrets` and `devops gh api` is a result that a consumer sees. So the change carries a spec delta.
- The delta adds three requirements to the capability `secret-masking`. The first keeps a quote mark that did not open the value. The second keeps an escaped quote mark and a double backslash whole. The third masks a value in a pair of quote marks with the pair.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: a quote mark, and an escaped quote mark, that did not open the value stay in the masked text.

## Impact

- `src/devops_cli/security/sanitizer.py`.
- `tests/security/test_secret_redaction.py`, `tests/security/test_redaction_properties.py` and `tests/commands/test_gh_cmd.py`.
- No command, option or message changes, so no generated documentation changes.

## Feasibility

- On `origin/main` at `5a4364c3`, `redact_text(json.dumps({"download_url": "https://example.com/o/r/f.txt?token=AGJ4EXAMPLE1234567890", "type": "file"}))` returned `...?token=<masked-token>, "type": "file"}`. `json.loads` of that text raised `JSONDecodeError: Expecting ',' delimiter`. The premise of the issue holds.
- A private repository is not needed. `devops gh api` passes the stdout of `gh` through `mask_secrets` (`src/devops_cli/commands/gh.py`, `api_cmd`), so a faked reply shows the same output.
- The cause is not the character class that the issue names. The value class `[^\s"',;]` already stops at a quote mark. The cause is the trailing `["']?` after the value, which matches a quote mark that no opening quote mark matched.
- The issue asks for a fix of the pattern for a query-string token. The same trailing `["']?` is in the rules for `password|passwd|pwd`, `aws_secret_access_key` and `client_secret`. The same run shows the same broken JSON for each of them. This answers the two open questions of the refine step.
- The rules for `api_key` and the other keywords of that rule pair their quote marks (`["'][...]["']` or no quote mark). Their run gave valid JSON, so they stay as they are.
- A conditional group of the `re` module in CPython 3.14.10 matches a closing quote mark only when the opening group matched. The group is `(?P<quote>["'])?` followed by `(?(quote)(?P=quote)?)`. A run of the fixed rules gives `...?token=<masked-token>","type":"file"}` for the reply above, and `json.loads` parses it.
- A value in quote marks, such as `token="AGJ4EXAMPLE1234567890" next`, still gives `token=<masked-token> next`.
- A review of the first fix found the escape defect. A run on the text `{"a":"curl \"https://x/f?token=abcdefgh12345678\"","b":1}` gave invalid JSON with the first fix and valid JSON on `origin/main`. The fixed value class gives valid JSON for it, for `password=hunter2hunter2\"`, and for a secret that ends in `\\`.
- A run of 100,000 backslashes through the new value class took 0.05 s, so the class does not backtrack in a harmful way.
- Issue #2471 (a rule must not cross a line break) is closed, and its fix is in the base. Pull request #3639 (issue #2613) and pull request #3676 (issue #2662) are merged. They changed `sanitizer.py`: the prose after a token colon stays unmasked, and a user name with no password is masked.
- This change touches the quote groups of the rules that #3639 changed, so it starts from the merged text. No open pull request touches `sanitizer.py`. The files of the six open pull requests were listed on 2026-11-05.

## Existing Tool Considered

The alternatives check of the issue (2026-11-04) found no tool that fixes this.

- JSON masking libraries mask by key on a parsed object. A log-redaction filter replaces whole matches in text, which is the behavior that takes the quote mark.
- The change uses the conditional group of the standard `re` module in the sanitizer that already exists. It adds one helper of three lines and one constant. It builds nothing new.
- The change deletes the four hand-written pairs of `["']?` from the patterns.
