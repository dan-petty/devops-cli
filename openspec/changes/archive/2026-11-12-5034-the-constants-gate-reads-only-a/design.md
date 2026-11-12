# Design

## Decisions

- **The digits stay whole.** `(?!\d)` after `(\d+)` stops the backtrack that turned `1790` into `179` when the lookahead `(?!-\d)` refused `1790`. The lookbehinds already refuse a start inside a number, so the regex now takes a whole number or nothing.
- **A value claim is the name, then `=`, `is` or `to`, then the number.** `_VALUE_LINK` allows a closing backtick after the name, an annotation such as `: Final[int]` before `=`, white space, and an opening backtick before the number. `_states_value` matches the link against the text that ends at the start of the number, so the number must follow the link with nothing between. These are the forms of the defect of #3200 and of the spec scenarios: "`SUMMARY_MAX_CHARS` is 40", `SUMMARY_MAX_CHARS = 40`, `SUMMARY_MAX_CHARS: Final[int] = 40`, and sets `SUMMARY_MAX_CHARS` to 40.
- **The other rules stay.** A sentence must still name one known constant and hold one candidate number. A sentence with two numbers stays ambiguous and is skipped, as the scenario "Two numbers in one sentence" asks. The link is an extra condition, so the gate can only refuse less.

## Rejected alternatives

- **Only the `(?!\d)` guard.** It removes the `179` of `lines 1790-2000`, but the operand `+ 1`, the option `-n 0`, `line 266` and the value of a new constant beside a known one still refuse good plans.
- **Remove the numbers inside code spans.** A code span holds the claim `SUMMARY_MAX_CHARS = 40` as often as an operand, so this drops real claims and keeps the prose cases such as `line 266`.
- **More link words, such as `of`, `at` or `holds`.** "Add `NEW_LIMIT` of 3 beside `KNOWN_LIMIT`" shows that `of` often gives a value to a new name, and the spec scenario "A bound after the constant name" reads `holds 60 characters` as no claim. #3388 is the place for claims in other words.
