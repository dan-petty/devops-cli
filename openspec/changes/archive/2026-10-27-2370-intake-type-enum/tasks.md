# Tasks

## 1. The proposal schema lists the values of each fixed field

- [x] Add failing tests: the schema of a request with types has the four enums and requires the four fields; it refuses an empty `type`; a request with no types keeps `type` as free text
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`
- [x] Add `proposal_schema(types)` with `create_model` and `Literal` fields, and send it from `GatewayIntakeModel.propose`
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py tests/test_roadmap_run.py`
- [x] Delete the second proposal request of intake, the `problem` field and its prompt sentence, with their tests; test that an off-list proposal skips its candidate after one request, and regenerate the prompt snapshot
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2370-intake-type-enum`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
