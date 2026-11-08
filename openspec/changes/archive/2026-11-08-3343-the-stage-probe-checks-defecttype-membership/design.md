# Design

## Decisions

- **Record the incident plan in the golden set as a good case.**: The merged plan holds no wrong finding type, so the claim is no defect of the plan. It uses the existing replay, adds no hand-rolled text check, and keeps the incident on record.
- **Record the `kind: placeholder` claim in one note of `case.json`.**: The note keeps the incident on record, and the case judges only the plan that the repository holds.
- **Do not add a scan of the plan prose.**: The scan refuses the sound plan of #3328 and finds no true hit in the 695 recorded plans. The model verifier covers the claim as `false_premise`.
- **Add the guard test in `tests/roadmap/stage/test_roadmap_stage_plan.py`.**: It proves that `check_proposal` accepts a plan that names a `DefectType` member, including one that the plan adds.
- **Add the case test in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.**: It proves that the incident case loads, holds the note, and passes every replay gate.

## Rejected alternatives

- **Add the scan with an exemption for a plan that changes the enum file.**: It keeps a text check with no measured hit and adds a second rule to keep that check sound.
- **Add the scan as the earlier plan wrote it.**: It refuses the sound plan of #3328, which adds a member of `DefectType` and names it.
- **Record the claim as a defect with the gate `none`.**: It marks a plan that merged as defective and adds an unjudged row for no code change.
- **Record the claim as a defect with the gate `pending`.**: `PENDING_GATES` is empty, so `_status` reports the defect stale and the replay fails.
