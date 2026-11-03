# Design

## Decisions

- **Measure and cut the delivery summary with `summary_length` from `pull_form.py`.**: The check `Semantic PR title` runs `^.{1,60}$` in JavaScript, which counts UTF-16 code units, and `summary_length` returns exactly that count. One helper then serves the form check, the stage title and the delivery title.
- **Cut the summary at a code point boundary, never between the two halves of a surrogate pair.**: `summary_length` counts an astral character as two units, so a cut at 60 units can land inside a character. A title with a lone surrogate is no text that a reader or the check can read.
- **Keep the `...` marker on a cut delivery summary.**: `tests/roadmap/test_roadmap_stage_title.py` asserts that the cut summary ends with `...`, and the issue asks for the measure and the cut boundary only, so the shape of the cut stays.
- **Change the `roadmap-implement-job` requirement `The pull request that delivers the code has the type of the issue` in this pull request, and give its scenario `A long summary` in code units.**: The specification states the limit that the code enforces. A specification that says characters while the code counts units contradicts the code and the check.
- **Add the emoji case and the exact-bound case to `tests/roadmap/test_roadmap_stage_title.py`.**: That module already holds the delivery title tests, and the file sits under `tests/roadmap/`, which mirrors `src/devops_cli/roadmap/`.

## Rejected alternatives

- **Keep `len` (Unicode code points) for the limit and the cut.**: `summary_length` in `src/devops_cli/roadmap/pull_form.py:42` adds one for each character above U+FFFF because JavaScript counts an emoji as two, so a code-point count accepts a title of 80 units that the check refuses (#3249).
- **Measure the summary in UTF-8 bytes.**: `summary_length` counts an astral character as two, not four, and the module docstring of `pull_form.py` states that the check's pattern runs in JavaScript over UTF-16 code units, so a byte count disagrees with the check in both directions.
- **Cut the title inside a surrogate pair and let the reader see a replacement character.**: The issue text of #3292 asks for a cut at a code point and no lone surrogate, and `summary_length` of a lone surrogate counts one, which no JavaScript title shows as a character.
- **Change the specification text in a separate issue.**: `openspec/specs/roadmap-implement-job/spec.md` holds the sentence `at most 60 characters` for the same limit that the code sets, so a separate change leaves the living spec contradicting the code until it lands.
