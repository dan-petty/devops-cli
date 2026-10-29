# Tasks

## 1. Each criterion is an OpenSpec requirement, and the proposal answers the existing-tool question

- [x] Add failing tests: a criterion with `name`, `requirement`, `scenario`, `when` and `then` validates; one with `description` or `verification` fails; a requirement without SHALL or MUST fails; a reply without `existing_tool` fails; `check_ready` is false for an empty `existing_tool` or an empty criterion part; the rendered section holds the requirement block and the `### Existing Tool Considered` answer and no `Criterion` or `Verification:` line; the reply prompt names every key of the model and both step prompts name `existing_tool`; an item that a person edited reaches the edit step with an empty proposal and no model call
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`
- [x] Change `AcceptanceCriterion`, add `existing_tool` to `RefinementProposal` and to the empty proposal of the edit step, change `check_ready`, `render_proposal_section` and the `refine_incomplete` message, and delete the old keys and lines
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py tests/test_ai_client_structured.py`
- [x] Name the new keys in `roadmap_refine_reply.md`, and ask the existing-tool question in `roadmap_refine_proposal.md` and `roadmap_refine_investigation.md`
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1849-refine-criteria-scenarios`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
