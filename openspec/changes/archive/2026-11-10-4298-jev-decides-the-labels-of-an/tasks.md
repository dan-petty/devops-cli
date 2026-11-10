# Tasks

## 1. Jev decides the proposal fields
Kind: behavior

- [x] 1.1 Write the failing tests of the Jev proposal, its fallback, its flags and its counter, and the Jev edge fake with its contract test
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_jev.py tests/ai/test_jev_edge_fake.py`
- [x] 1.2 Add `JevIntakeModel`, the setting `roadmap.intake.jev`, the constants, the messages and the counter, and pass `needs_type` and `type_notes` from the planner
  - Verification: `$ uv run devops ci test tests/roadmap/intake`

## 2. The comparison with the triage model
Kind: behavior

- [x] 2.1 Write the failing tests of the label set, the scores and the report, and of `devops roadmap eval jev`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_eval.py tests/commands/test_roadmap_eval_jev.py`
- [x] 2.2 Add `jev_eval`, the label set and the command `devops roadmap eval jev`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_eval.py tests/commands/test_roadmap_eval_jev.py`

## 3. Documents
Kind: other

- [x] 3.1 Regenerate the reference documents and describe the setting, the counter and the command in the intake page
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
