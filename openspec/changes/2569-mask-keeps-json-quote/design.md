# Design

## Context

See `proposal.md`. `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` holds the keyword rules. Four of them allow an optional quote mark before the value and an optional quote mark after it, and the two are not tied. A value in a URL query inside a JSON string has no opening quote mark, and the rule takes the closing quote mark of the string.

## Goals / Non-Goals

**Goals:**

- Masked JSON text is still valid JSON when a secret in a string was masked.
- A value in a pair of quote marks, and a bare value, are masked as before.

**Non-Goals:**

- The text that a masked value swallows after it. A value ends at a space, a quote mark, a comma or a semicolon, so `?token=<value>&page=2` loses `&page=2`. The rule fails closed, and the text stays valid JSON inside a string.
- A new JSON-aware masking path. See decision 2.

## Decisions

### 1. Tie the closing quote mark to the opening one in the pattern

`_quoted(value)` wraps the pattern of a value in `(?P<quote>["'])?`, the value, and `(?(quote)(?P=quote)?)`. The closing quote mark is part of the match only when the group `quote` matched, and it must be the same mark. The four rules call it.

- *Rationale*: the loss comes from a pair of independent optional groups. A conditional group of the `re` module states the pair in the pattern, with no change to the replacement.
- *Rationale*: the closing quote mark stays optional when a quote mark opened the value. A value that starts with a quote mark and has no closing mark is still masked, as before. A required closing mark would leave such a secret in the text.
- *Rejected alternative*: add the quote marks to the character class of the value, as the issue proposes. The class `[^\s"',;]` already excludes both marks, so the value stops at the quote mark today. A run of the rules on the issue's reply shows that the trailing `["']?` takes the mark, so the class is not the cause.
- *Rejected alternative*: a lookahead that ends the match before every quote mark. A value in a pair needs its closing mark inside the match. Without it, `password: "correcthorse"` gives `password=<masked-password>"`, with an unpaired mark, and the tests that hold the pair fail. The conditional keeps both cases.
- *Rejected alternative*: keep the match and write the quote mark back in the replacement. The replacement would need to know whether a quote mark opened the value, and the literal replacements of `aws_secret_access_key` and `client_secret` would become callables. The conditional needs no code outside the pattern.

### 2. Fix the rules, not the `devops gh api` command

The change stays in the sanitizer. The command keeps `mask_secrets(res.stdout)`.

- *Rejected alternative*: parse the reply as JSON in `devops gh api`, mask each string with `mask_dict_secrets`, and write the JSON again. A reply is not always one JSON document: `--jq` prints one value for each line, `--template` prints text, and `--paginate` prints the documents of the pages one after another. The same defect also stays in every other caller of `mask_secrets` on JSON text. The pattern is the one cause.

### 3. Fix every rule that has the defect

The rules for `password|passwd|pwd`, `aws_secret_access_key` and `client_secret` have the same unpaired `["']?`, and a run of each gives broken JSON for a value in a query. One helper writes the pair, so a fifth rule cannot copy the defect.

- *Rejected alternative*: fix only the `token` rule, which the issue names. The other three rules would still break JSON for the same input, and the issue would come back with another keyword.

## Risks / Trade-offs

- [Risk] A value that one kind of quote mark opened and the other kind closes, as in `token='<value>" next`, keeps the second mark. The masked text shows a mark with no pair.
  - Mitigation: the mark was in the input, and the change adds none. The secret is masked. A test holds the case.
