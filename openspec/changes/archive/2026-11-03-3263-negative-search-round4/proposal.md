# Proposal

## Why

Refs #3263. The review of the third pull request for #3263 found two major and four smaller defects.

1. The rule for a refused verification command ran after the rules for OOM, timeout, conflict, parser and provider, and those rules search the echoed command. A refused `python -m pytest tests/roadmap/test_rate_limit.py` gave `provider` / `retry`, and a refused search with `'timed out'`, `-k 'out of memory'` or `-k 'merge conflict'` gave `timeout`, `oom` and `conflict`. A plan that can never pass was retried.
2. The output of a command went raw into the stop reason through `_tail`. A file with ESC, U+202E and NEL that a negative search matches reached `outcome.reason` as it was. The spec said the reason holds no raw control character, which was wider than the code.
3. `! git grep -n devops README.md/` passed the gate and the step. A trailing slash on a file matches nothing in git, and `StagedTree.has` strips the slash.
4. A NUL byte or a lone surrogate in a word of an allowed program raised `ValueError` or `UnicodeEncodeError` out of `commands_failure`, while the gate accepted it.
5. Two test holes: the message for a backtick, and the fallback to the words of a refused or unreadable command.
6. Nits: two long docstring lines, the name `CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS` and its note still said "negative search", and a local name `shown` hid the imported function.

## What Changes

- `classify_failure` reads the rule for a refused verification command first, anchored at the start of the text. A word in the command no longer changes the class.
- `_tail` escapes each line of the output with `shown` and cuts it to the reason limit. The spec now says that the command, the words and the output are escaped.
- A path that ends in `/` has to be a folder of the staged commit. A file with a trailing slash is a problem at plan time.
- `read_verification` refuses a word with a NUL byte or a character that does not encode, with a reason, in the step and in the gate.
- New tests for the backtick message and for the fallback to the words of the command.
- The constant is `CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS`. The docstrings are wrapped. The local name in `_paths_text` is `listed`, and the parameter of `_command_failure` is `named`.
- Observable behavior changes, so the change carries a spec delta. The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`, `roadmap-stage`, `roadmap-failure-taxonomy`.

## Impact

- Code: `failure.py`, `implement_shell_policy.py`, `implement_step.py`, `stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`.
- Tests: `test_roadmap_failure.py`, `test_roadmap_stage_paths.py`, `test_roadmap_implement_verification_reason.py`, `test_roadmap_limit_classes.py`.

## Feasibility

- Each defect was reproduced by the review, and the new tests fail on origin/main for those reasons: the class of the four commands, the raw bytes in `outcome.reason`, the trailing slash on `README.md/`, and the exceptions for a NUL byte and `\ud800`.
- A file with the line break NEL (U+0085) is split by `str.splitlines` in `_tail`; each part is escaped, so the escape holds for the output of any program.

## Existing Tool Considered

`str.encode("unicode_escape")` (already used by `shown`) and `re` cover the need. No library is added. The change builds about 40 lines of source and 150 lines of tests: roughly 35000 tokens to build and fix, 1500 tokens a year to keep, and about 1.5 hours. It deletes the alternative for a refused command in the cause rules.
