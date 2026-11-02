# Tasks

## 1. Name the lesson in SECURITY.md

Reads: `SECURITY.md` rule 12. Changes: `SECURITY.md`.

This group changes one document. The repeatable check is the `git grep` in 1.1.

- [x] 1.1 Verify that `git grep -n "supports_native_structured_output" -- SECURITY.md` prints nothing before the change and one line after it
- [x] 1.2 Add the sentence to rule 12, and verify that `uv run devops ci docs` passes
