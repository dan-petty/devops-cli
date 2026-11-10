# Proposal: #4314

## Why

The trace gate refuses a plan whose Feasibility sentence says what code does (#4314). `_READ_WORD` in `src/devops_cli/roadmap/stage/stage_change.py` matches `reads` and `reading` anywhere in a sentence, so "because it reads `.github/labels.yml` of the default branch" counts as a claim that the run read the path. A live stage run on #3599 with the live stage model was refused with "The Feasibility section states that `.github/labels.yml` was read, but the run did not read it." The subject of `reads` was the function. Closes #4314.

## What Changes

- A `reads` or `reading` that has a code span, `it` or `which` as its subject is no claim that the run read a path.
- A claim of the run or of the author (`I read`, `the run read`, `the run reads`, `after reading`, `read_file`) is refused as before when the trace holds no call for the path.
- The change carries a spec delta because it changes which plans the stage job refuses.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Code that reads a file is no claim of the run

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`

## Feasibility

- The cause is in the code: `_uncalled_path` searched `_READ_WORD` in the sentence with its code spans blanked, and used no word before the verb. The sentence of the live run is the test input, word for word.
- The reply is kept in the refused-reply file of the run: the first refused reply of #3599 holds the sentence "Precondition of `declared_labels(self.store, ref=None)`: a client of the GitHub service, because it reads `.github/labels.yml` of the default branch."
- First check against the real system: `uv run devops roadmap eval stage --replay`, which keeps 81 of 317 defects caught by a gate, 0 missed, and 5 of 5 good plans accepted.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_subject.py tests/roadmap/stage/test_roadmap_stage_trace_spans.py`.

## Existing Tool Considered

No library reads the subject of a sentence for a gate of this size, and the project holds no such helper. The change adds one pattern for the words before `reads` and one function that applies it. Cost: about 20 000 tokens to build, 3 000 to keep and 1 hour. The change deletes no internal code.
