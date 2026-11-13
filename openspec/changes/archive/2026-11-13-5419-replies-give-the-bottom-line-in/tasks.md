# Tasks

## 1. The style rules ask for the bottom line in the first line

Kind: behavior. Reads: `src/devops_cli/ai/client/style_request.py`. Changes: `src/devops_cli/ai/tasks/style_ste100.md`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/__snapshots__/test_ai_client_style_request.ambr`.

- [x] 1.1 Write the failing test: the request that `with_style_request` builds holds each sentence of the first-line rule
  - Verification: `$ uv run devops ci test tests/ai/test_ai_client_style_request.py`
- [x] 1.2 Change the paragraph of `style_ste100.md` that started "Put the result and the decision first", and regenerate the snapshot of the request with `uv run pytest tests/ai/test_ai_client_style_request.py --snapshot-update`
  - Verification: `$ uv run devops ci test tests/ai/test_ai_client_style_request.py tests/ai/test_ai_task_loader.py tests/ai/client`

## Workflow follow-up

- #5146 corrects the snapshot command of `docs/TESTING.md`: syrupy 7.0.0 has no option `--snapshot-file-lock`, and it locks the snapshot file by itself under xdist.
- #5424 adds the style request to the pydantic-ai agent runs (`devops ai chat`, `investigate` and the implement step), which send none, so they get this rule too.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
