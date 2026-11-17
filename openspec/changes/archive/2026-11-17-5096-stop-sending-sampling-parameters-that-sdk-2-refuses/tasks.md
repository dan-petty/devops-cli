# Tasks

## 1. Behavior

- [x] 1.1 Write the failing HTTP-seam test that forces SDK 2 and refuses sampling fields.
  - Verification: `$ uv run devops ci test tests/ai/client/test_claude_provider.py`
- [x] 1.2 Omit `temperature` and `top_p` when the installed SDK major is 2 or later.
  - Verification: `$ uv run devops ci test tests/ai/client/test_claude_provider.py`
- [x] 1.3 Keep the SDK 1 sampling path, proven by a test.
  - Verification: `$ uv run devops ci test tests/ai/client/test_claude_provider.py`

## 2. Documents

- [x] 2.1 Update the `ai-model-sampling` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 5096-stop-sending-sampling-parameters-that-sdk-2-refuses`
