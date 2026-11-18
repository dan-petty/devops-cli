# Tasks

## 1. Trace Gate Updates

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, `openspec/specs/roadmap-stage/trace-gate/spec.md`.

- [x] 1.1 Update `_NEGATION`, `_CODE_READS`, `_PLURAL_CODE_READ`, `_is_code_reading`, `_citation`, and `_object_span` in `src/devops_cli/roadmap/stage/stage_change.py`
  - Verification: `$ uv run python /home/vscode/.gemini/antigravity/brain/7d0d7f0d-1fa3-4365-9202-bddd7e57c136/scratch/repro_4590.py`
- [x] 1.2 Add unit test cases to `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_trace_subject.py`
- [x] 1.3 Update specification in `openspec/specs/roadmap-stage/trace-gate/spec.md`
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: The trace gate SHALL not judge the last path before a relative-clause read whose object holds no path.
- Group 1: The trace gate SHALL not treat a code subject with a file citation in parentheses as a read by the run.
- Group 1: The trace gate SHALL recognize a list of code spans as a code subject before a read verb.
- Group 1: The trace gate SHALL treat `cannot` as a negation word in read claims.
- Group 1: The trace gate SHALL strip trailing ` <start>-<end>` line ranges from path citations.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
