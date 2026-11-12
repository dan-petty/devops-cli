# Proposal: #5069

## Why

The constants gate of the stage job still refuses good plans in two forms after #5042. A correct quote of `CONST_AGENTS_MD_MAX_CHARS: Final[int] = 6_500` gives "the plan says 6": `(\d+)` takes `6`, and the lookbehind drops `500`. #5034 lists this false refusal (#1336), and the stage prompt asks the model to cite the staged value of each constant. A new value after `to`, such as "Raise `NAME` to 80" or "The test patches `NAME` to 1", always differs from the staged value, because the staged tree is the commit before the change. #5042 put this refusal into the spec and into a test. Closes #5069.

The archived change of #5034 holds two false claims. It says that the change adds no refusal, but a sentence that held a range and a value claim is now checked. It says that the gate was made for the #3200 defect, but neither the old nor the new gate refuses the real #3200 plan. So the gate has no recorded true positive.

## What Changes

- `_CANDIDATE_NUMBER` in `src/devops_cli/roadmap/stage/stage_constants.py` takes a Python integer literal with `_` digit separators as one number: `(\d+(?:_\d+)*)`, with `(?![\d_]|[/.]\w|-\d)` after it. `int()` reads `6_500` as 6500.
- `_VALUE_LINK` has no `to`. The gate compares a number only when it follows the constant name with `=` or `is`.
- The requirement "A plan number beside a constant matches the staged value" of `roadmap-stage/claims` states the two rules, with scenarios for a literal with digit separators and for a new value that the change sets.

## Capabilities

- `roadmap-stage/claims`: the constants gate reads a literal with digit separators as one number and does not compare a new value after `to`.

## Impact

- The gate refuses fewer plans. A quote of a digit-separated literal that matches the staged value passes, and a quote that differs gives one problem with the whole number (6400, not 6).
- A plan that changes a constant ("Raise `NAME` to 80") passes. A wrong new value after `to` is no longer refused. #3388 adds structured claims that keep a current value apart from a new value.
- A value claim with `is` or `=` that differs from the staged tree is still refused: `` `NAME` is 40 ``, `` `NAME` is `40` ``, `NAME = 40`, `NAME == 40` and `NAME: Final[int] = 40`. A new value with `=`, such as "Change the line to `NAME: Final[int] = 40`", is still refused.
- Since #5042, the gate also accepts these forms, which the gate before #5042 refused: "is set to 40", "SHALL be 40", "must be 40", "defaults to 40", "(40)", "equals 40", "is now 40", "which is 40", "becomes 40", `` `NAME`: 40 ``, a table row `` | `NAME` | 40 | `` and "`NAME` and 40". This change adds the `to` forms. The gate has no recorded true positive, so the trade is acceptable until #3388.
- A sentence that names a constant and holds a line range and a value claim, such as "Lines 3410-3420 of `constants.py` hold `NAME = 40`", has one candidate number since #5042, so the gate checks it. The gate before #5042 found two numbers and skipped the sentence.

## Feasibility

- `origin/main` at cf4733e00 holds `_CANDIDATE_NUMBER = re.compile(r"(?<![#:\w/.])(?<!\d-)(\d+)(?!\d|[/.]\w|-\d)")` and ``_VALUE_LINK = r"`?(?:\s*:\s*[\w.\[\]]+\s*=|\s*(?:==?|is\b|to\b))\s*`?"``.
- `src/devops_cli/config/constants.py:195` holds `CONST_AGENTS_MD_MAX_CHARS: Final[int] = 6_500`. 18 module-level constants in `src/` use `_` digit separators.
- `constant_problems(["constants.py:195:CONST_AGENTS_MD_MAX_CHARS: Final[int] = 6_500"], {"CONST_AGENTS_MD_MAX_CHARS": 6500})` on cf4733e00 gives `CONST_AGENTS_MD_MAX_CHARS is 6500 in the staged tree, but the plan says 6.` The quote with `6_400` gives the same text. The gate before #5042 (16356d817) gives the same two results.
- With `{"CONST_X": 30}`, cf4733e00 refuses "Raise `CONST_X` to 40.", "Set `CONST_X` to 40 in `constants.py`." and "The test patches `CONST_X` to 1 so each run stops." It accepts "Raise `CONST_X` from 30 to 40." only because that sentence holds two numbers.
- `src/devops_cli/roadmap/stage/stage.py:1832` reads `staged_constants(self._source, self._sha, ...)`, and the comment at line 1846 says that the citation rule reads the staged commit. That commit is the commit before the change.
- The first plan of #3200 (7a9388f43) names `SUMMARY_MAX_CHARS` in a requirement and gives "the 40-character bound" in a separate THEN line. `constant_problems` over its added lines with `{"SUMMARY_MAX_CHARS": 60}` gives no problem on 16356d817 and on cf4733e00.
- `uv run devops roadmap eval stage --replay` holds no case with recorded constants. It gives the same result on cf4733e00 and on this change: 5 of 5 good plans pass, and every gate refuses what it must refuse.

## Existing Tool Considered

Python `re` holds the rule, and Python `int()` reads the `_` digit separators. The change adds no library. No open library reads a value claim about a named constant from plan prose; #3388 replaces the prose scan with a structured field. Cost to build: about 60,000 tokens and 1 hour; to keep: about 1,000 tokens a month.
