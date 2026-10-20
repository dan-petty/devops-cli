# Task: Suppression Comments May Not Grow Unnoticed (#849)

**Issue**: [#849](https://github.com/dan-petty/devops-cli/issues/849)
**Feasibility**: Verified against Python 3.14 `tokenize.generate_tokens` (C-accelerated tokenizer), `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `pyproject.toml`, and `tests/test_architectural_invariants.py`; confirmed comment-token scanning with a raw-text pre-filter completes in ~0.48 s across all `src/` and `tests/` modules without false positives on string literals or `'nanosecond'` prose comments.

## Summary

- Defined suppression kind constants (`CONST_SUPPRESSION_KINDS`, `CONST_COMMENT_SUPPRESSION_KINDS`, `CONST_PYPROJECT_SUPPRESSION_KINDS`) and comment-token regular expressions in `src/devops_cli/config/constants.py`.
- Defined `DEFAULT_SUPPRESSION_CEILINGS` and `DEFAULT_NET_CONSTRUCT_SUPPRESSION_CEILING` in `src/devops_cli/config/defaults.py`, set to exact current counts across `src/`, `tests/`, and `pyproject.toml`, and lowered `DEFAULT_C901_SUPPRESSION_CEILING` from `65` to `51` to match the current count.
- Added `test_suppressions_stay_under_their_ceilings` and companion unit tests in `tests/test_architectural_invariants.py` that count `type: ignore`, per-rule-code `noqa`, `nosec`, `pragma: no cover`, `pragma: no mutate`, file-level directives, and `ast-grep-ignore` (`net-*` rule IDs in `src/`) from `tokenize.COMMENT` tokens alongside `per-file-ignores`, `[[tool.mypy.overrides]]`, and coverage `omit` entries from `pyproject.toml`.

## Acceptance Criteria

- [x] One test in `tests/test_architectural_invariants.py` counts, with `tokenize` (comment tokens only), over `src` and `tests`: `type: ignore`, `noqa` per rule code, `nosec`, `pragma: no cover`, `pragma: no mutate`, file-level directives, and `ast-grep-ignore` per `net-*` rule ID (`tests/test_architectural_invariants.py::test_suppressions_stay_under_their_ceilings`).
- [x] From `pyproject.toml` it also counts `per-file-ignores` entries, `[[tool.mypy.overrides]]` blocks, and coverage `omit` entries (`tests/test_architectural_invariants.py::test_every_comment_and_pyproject_suppression_kind_is_counted`).
- [x] The kinds live in `src/devops_cli/config/constants.py` and the ceilings in `src/devops_cli/config/defaults.py`, set to the counts at merge, with each check enforcing `count <= ceiling`.
- [x] Adding one `# type: ignore` to a module in `src` fails the test, naming the kind, the ceiling, and the file, and instructing to fix the cause or raise the ceiling with a reason recorded in the task file (`tests/test_architectural_invariants.py::test_adding_a_type_ignore_in_src_fails_naming_kind_ceiling_and_file`).
- [x] A fixture with `'nanosecond'` in a comment is not counted (`tests/test_architectural_invariants.py::test_nanosecond_comment_and_string_literals_are_not_counted`).
- [x] Removing a suppression keeps the test green (`tests/test_architectural_invariants.py::test_removing_a_suppression_keeps_the_ceiling_check_green`).
- [x] The test runs in at most 1 s, with no new dependency.
