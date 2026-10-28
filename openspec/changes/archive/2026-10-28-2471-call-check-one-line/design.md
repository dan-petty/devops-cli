# Design

## Context

See `proposal.md`. The `api_key` rule of `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` ends an unquoted value with the call check `(?!\s*\()`. The check reads past the end of the line, so the next line decides the result for the line of the value.

## Goals / Non-Goals

**Goals:**

- The text after a line break does not change the result for the line before it, in the data and code syntax.
- A call on the same line as the keyword stays unmasked, as it does now.
- Each whitespace class that joins a keyword, its separator and its value has a test that fails when the class changes.

**Non-Goals:**

- The requirement names LF and CR as line breaks. Other characters that `str.splitlines` takes as a line boundary, such as a form feed, `\x85` or `\u2028`, stay whitespace on one line for these rules.

## Decisions

### 1. `(?![^\S\r\n]*\()` after an unquoted value

The call check allows whitespace that is not a line break before the `(`.

- *Rationale*: a `(` on the same line, also after a space or a tab, continues to mark a call. A line break ends the check, so the next line has no effect.
- *Rejected alternative*: delete the check. On `origin/main` at `960e3573`, the rule with no check turned `api_key=settings_mod.get_ai_api_key(st))` into `api_key=<masked-api-key>(st))`, which `test_mask_secrets_preserves_function_invocations` refuses. A review then sees a masked value where the code calls a function.
- *Rejected alternative*: `(?!\()`, with no whitespace. On the same tree, it turned `api_key = settings_mod.get_ai_api_key (st)` into `api_key=<masked-api-key> (st)`. That changes the result for a call on one line, which this change must not do.

### 2. A property test for the next line

A Hypothesis property takes each credential line of the tests, a line break and any text with no line break. It asserts that `redact_text` of the joined text equals `redact_text` of the credential line, the line break and `redact_text` of the text.

- *Rationale*: docs/TESTING.md tests redaction with Hypothesis properties. The property states the requirement for any next line, not only for the lines that a test author thinks of. Explicit examples hold the `(` lines of #2471.
- *Rejected alternative*: examples only. They test only the next lines that the author thinks of, and #2450 missed the `(` line.

## Risks / Trade-offs

- [Risk] A code style that puts the `(` of a call on the next line, after an `api_key` value, is now masked. → Mitigation: Python and the common formatters keep the `(` of a call on the line of the function name. A masked value in a review excerpt shows less code, but it never shows a secret.
