# Task: The docs check validates the options inside optional-group brackets (#1299)

**Issue**: [#1299](https://github.com/dan-petty/devops-cli/issues/1299)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p3-low
**Scope**: type/bug, scope/docs, priority/p3-low

## Description

`is_placeholder` in `src/devops_cli/docs/markdown_argv_collector.py` treats every word that starts with `[` or ends with `]` as a placeholder, and the resolver lets a placeholder stand for any number of tokens. An option written inside a synopsis optional group, such as `[-v` or `[--no-such-flag]`, was therefore never checked, so a misspelled option there passed `devops docs check`. The hole came in with #921.

Requiring a matched bracket pair was rejected: `shlex` splits `[-v <ver>]` into `[-v` and `<ver>]`, so neither word carries both brackets and the synopsis lines in `RELEASE_CYCLE.md` would stop resolving.

The fix is `_argv_token`, which `_tokenize_command` now calls for each word. It removes one leading `[` and one trailing `]`; a word that then starts with `-` is that option and goes to the resolver as a literal. Every other word keeps the existing `is_placeholder` mapping, so `<ver>]`, `INT]`, `[OPTIONS]` and `[ARGS]...` stay placeholders.

With the fix, the `-p` and `-v` options in the `devops release` table of `RELEASE_CYCLE.md` (lines 141-145) are checked against the command tree, and they resolve. All checked docs stay at 0 findings.

## Acceptance Criteria

- [x] `[-v <ver>]` resolves with `-v` checked as an option, and `[--no-such-flag]` is reported as an unknown option: `test_an_option_in_optional_group_brackets_is_validated` in `tests/test_docs_knowledge_base_argv.py`.
- [x] `changelog.d/1299.md` records the fix under `### Fixed`. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
