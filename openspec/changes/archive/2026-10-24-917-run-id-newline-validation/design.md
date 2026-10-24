# Design

## Context

See `proposal.md` for motivation.
Several modules validate identifiers using regular expressions anchored with `^` and `$`.
In Python, the `$` anchor matches before a trailing newline character.
This allows identifiers with trailing newlines to pass validation.

## Goals / Non-Goals

**Goals:**

- Reject identifiers that contain trailing newlines in `get_run`.
- Ensure `get_run` returns `None` without executing filesystem glob operations when given invalid identifiers.
- Replace `re.match` with `re.fullmatch` in identifier validation checks across `src/`.

**Non-Goals:**

- Do not alter multi-line text search patterns or line-oriented regex parsing (such as markdown headings or log parsers).
- Do not add backward compatibility for strings that contain unexpected newlines.

## Decisions

- **Use `re.fullmatch` for identifier validation.** `re.fullmatch` requires the entire string to match the specified pattern. Trailing newline characters do not match.
  - *Rejected Alternative:* Use `\Z` with `re.match`. Evidence: `\Z` requires raw string syntax or escaped backslashes and is less explicit than `re.fullmatch`.
  - *Rejected Alternative:* Call `.strip()` on input before `re.match`. Evidence: `.strip()` quietly alters inputs instead of rejecting invalid identifiers. It also masks caller bugs.
- **Mock filesystem globbing in test.** Test asserts that `get_run("abc\n")` returns `None` and does not invoke `Path.glob`.
  - *Rejected Alternative:* Rely only on the return value of `get_run`. Evidence: On unpatched code, `get_run("abc\n")` also returns `None` after globbing finds no matching file. A mock proves that `get_run` rejects the identifier before globbing.

## Risks / Trade-offs

- [Callers passing identifiers with unstripped newlines now fail validation] → This is intended behavior. Callers must pass clean identifiers.
