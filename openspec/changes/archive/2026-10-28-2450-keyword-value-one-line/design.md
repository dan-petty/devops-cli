# Design

## Context

See `proposal.md`. `_build_secret_patterns` in `src/devops_cli/security/sanitizer.py` makes the data and the code pattern sets. Seven of its patterns join a credential keyword or a separator to a value with `\s*` or `\s+`, so a value can start on the next line.

## Goals / Non-Goals

**Goals:**

- A credential keyword or separator and its value sit on one line, in the data and code syntax.
- Every one-line pair keeps its result.

**Non-Goals:**

- The private key pattern continues to cover many lines, because a PEM block starts and ends on different lines.
- The phrase `google service account` is not a keyword with a value, so its pattern does not change.
- The check after an `api_key` value for a call, `(?!\s*\()`, reads after the value and does not join a keyword to a value, so it does not change.

## Decisions

### 1. `[^\S\r\n]` between a keyword and its value

Each keyword-to-value pattern uses `[^\S\r\n]` in place of `\s`. This class matches each whitespace character that `\s` matches, but not LF and CR.

- *Rationale*: only a line break changes its result. A keyword and its value on one line are masked as before, for each separator that `\s` matched.
- *Rejected alternative*: `[ \t]`, which issue #2450 proposes. On `origin/main` at `95eb8b68`, `redact_text("password:\xa0hunter2hunter2")` returned `"password=<masked-password>"`, because `\s` matches the no-break space. `[ \t]` does not match it, so a one-line pair with a no-break space would no longer be masked. That lowers the masking, which a security change must not do.

### 2. Change the patterns, not the input

The fix changes the patterns.

- *Rejected alternative*: apply the patterns to each line apart (`str.splitlines`). The private key pattern must see all the lines of a PEM block, from `-----BEGIN` to `-----END`, so a split per line stops it.

## Risks / Trade-offs

- [Risk] A value that a file writes on the line after its key, such as a YAML plain scalar that continues on the next line, is no longer masked by a keyword rule. → Mitigation: the rules for known token formats (GitHub, OpenAI, Anthropic, AWS key ID, JWT, Vault, GitLab, Hugging Face) match the value itself, with no keyword, so they continue to mask it.
