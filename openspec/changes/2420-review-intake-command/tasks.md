# Tasks

## 1. A session that is not on merged code says why

- [x] Add failing tests: the reason of each session kind, and the `review path` line of a clean and of a dirty session
  - Verification: `uv run devops ci test tests/review/test_review_intake_handoff.py`
- [x] Add `why_not_on_merged_code`, and make `is_on_merged_code` its test for no reason
  - Verification: `uv run devops ci test tests/review/test_review_intake_handoff.py tests/review/test_review_on_merged_code.py`

## 2. The candidate of a qualifying finding

- [x] Add failing tests: which findings qualify, and the candidate of a verified ruff finding
  - Verification: `uv run devops ci test tests/review/test_review_intake_handoff.py`
- [x] Add `review/handoff.py` with the qualifying test and the candidate, and give the fingerprint v2 pattern one home in `review/fingerprint.py`
  - Verification: `uv run devops ci test tests/review/test_review_intake_handoff.py tests/test_review_filed_findings.py`

## 3. The hand-off and the command

- [x] Add failing tests: a confirm run files only the finding no issue carries; a plan writes nothing; a refused session; a secret in a candidate; the dry run; a plan with every finding filed; more than one mode flag
  - Verification: `uv run devops ci test tests/review/test_review_intake_handoff.py`
- [x] Add the hand-off, `ReviewHandOffRefusedError`, the `devops review intake` command and the `review path` line, and let the model fake embed through the `Embedder` protocol
  - Verification: `uv run devops ci test tests/review/test_review_intake_handoff.py tests/review/test_review_on_merged_code.py`
- [x] Route merged-code findings through the command in `docs/SELF_IMPROVEMENT.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 4. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2420-review-intake-command`

## Workflow follow-up

- The hand-off of one CONFIRMED finding from `devops review verify`, and CONFIRMED findings in `devops review intake`, wait for #2414, which stores a finding's state.
- The MCP `review_path` tool does not name the hand-off. A person or agent runs `devops review intake` after an MCP review.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
