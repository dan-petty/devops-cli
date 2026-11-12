# Proposal: #5034

## Why

The constants gate of the stage job refuses good plans. `constant_problems` takes a sentence that names one known constant and holds one candidate number, and it compares that number with the staged value. It does not check that the plan gives that number to the constant. The number regex also has no guard after the digits, so `lines 1790-2000` gives `179`. The recorded refused reply of #4472 got 5 false problems from this gate, and the recorded reply of #4043 gets 3. The only real defect that the gate was made for (#3308) is a value claim, such as "`SUMMARY_MAX_CHARS` is 40" in the plan of #3200. Closes #5034.

## What Changes

- `_CANDIDATE_NUMBER` in `src/devops_cli/roadmap/stage/stage_constants.py` gets `(?!\d)` after the digits, so a range such as `1790-2000` gives no number.
- `constant_problems` compares the one candidate number of a sentence only when the number follows the constant name with `=`, `is` or `to`: `NAME = 40`, `NAME: Final[int] = 40`, `` `NAME` is 40 `` and sets `` `NAME` `` to 40. An operand (`NAME + 1`), an option value (`-n 0`), a line number and the value of another name in the sentence are no value of the constant.
- The requirement "A plan number beside a constant matches the staged value" of `roadmap-stage/claims` states the link, with scenarios for the texts of #4472 and #4043.

## Capabilities

- `roadmap-stage/claims`: the constants gate compares only a number that the plan gives to the constant.

## Impact

- The gate refuses fewer plans. Each sentence that it refused before and refuses now is a value claim with `=`, `is` or `to`; the change adds no refusal, because it only removes candidate numbers.
- The recorded replies of #4472 and #4043 give no constants problem. A plan that says "`SUMMARY_MAX_CHARS` is 40" while the tree holds 60 is still refused.
- A sentence that puts a wrong number beside a constant with no `=`, `is` or `to`, such as "`SUMMARY_MAX_CHARS` and 40", is no longer refused. #3388 adds structured constant claims for this case.

## Feasibility

- `origin/main` at 87ae9eefa holds `_CANDIDATE_NUMBER = re.compile(r"(?<![#:\w/.])(?<!\d-)(\d+)(?![/.]\w|-\d)")` and `numbers = [int(m.group(1)) for m in _CANDIDATE_NUMBER.finditer(sentence)]` in `constant_problems`, with no check of the text between the name and the number.
- `constant_problems` on main, run over each sentence of the recorded refused reply of #4472 (2026-11-11), gives `DEFAULT_CI_TEST_SERIAL_MAX_FILES is 12 in the staged tree, but the plan says 179.` (`lines 1790-2000`), `... says 1.` (`DEFAULT_CI_TEST_SERIAL_MAX_FILES + 1`), `DEFAULT_CI_TEST_NARROWED_WORKERS is 4 in the staged tree, but the plan says 0.` (`-n 0`, two sentences) and `... says 50.` (`DEFAULT_CI_TEST_SERIAL_MAX_TESTS: Final[int] = 50` beside it).
- The same run over the recorded reply of #4043 gives `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS is 30 in the staged tree, but the plan says 3.`, `266` and `267` (a new constant "of 3", and `at line 266`).
- The Service logs from 2026-11-08 to 2026-11-11 hold constants problems for #3569 (137092), #3570 and #4043 (10), #1336 (6), #3388 (11) and #4472. None of the numbers is a value that the plan gives to the named constant.
- `uv run devops roadmap eval stage --replay` holds no case with recorded constants, so the replay gives the same result on main and on this change.

## Existing Tool Considered

Python `re` holds the rule, and the change adds no library. No open library reads a value claim about a named constant from plan prose. #3388 replaces the prose scan with a structured field and keeps the scan as a fallback, so this fix stays useful after #3388. Cost to build: about 120,000 tokens and 2 hours; to keep: about 2,000 tokens a month.
