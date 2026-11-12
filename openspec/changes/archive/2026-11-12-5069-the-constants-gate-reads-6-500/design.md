# Design

## Decisions

- **A literal with digit separators is one number.** `(\d+(?:_\d+)*)` takes `6_500` whole. The lookahead `(?![\d_]|[/.]\w|-\d)` refuses a `_` after the digits, so the engine does not backtrack from `6_500` to `6`, and `6_` gives no number. The lookbehind `(?<![#:\w/.])` already refuses a start after `_`. Python `int()` accepts the separators, so the gate compares 6500.
- **Only `=` and `is` link a value to a constant.** The gate compares the plan with the staged tree, and the staged tree is the commit before the change. A number after `is` or `=` states the current value. A number after `to` is the new value that the change sets ("Raise `NAME` to 80") or a value that a test sets ("patches `NAME` to 1"), so it differs from the staged value when the plan is correct.
- **The other rules stay.** A sentence must still name one known constant and hold one candidate number, and the number must follow the link with nothing between.

## Rejected alternatives

- **Keep `to` and skip the verbs of a change, such as raise, set and patch.** A list of verbs is a second prose parser, and it misses forms such as "change the bound to 80". #3388 adds structured claims that keep a current value apart from a new value.
- **Read a new value with `=` as a change too.** "Change the line to `NAME: Final[int] = 40`" quotes a new line, but `NAME = 40` in a code span is also the most common quote of the staged line. The gate keeps `=` as a claim of the current value.
- **Add `is set to` and `defaults to` to the link.** These forms state a current value as often as a new one. The gate has no recorded true positive, so the change adds no link word.
