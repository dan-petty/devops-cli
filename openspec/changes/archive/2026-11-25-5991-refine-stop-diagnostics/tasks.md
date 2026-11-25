# Tasks

## 1. Behavior

- [x] 1.1 Add failing `FunctionModel` tests for `<text>` tool retry diagnostics and `NativeOutput` text-part stop diagnostics in `tests/roadmap/refine/test_roadmap_refine_investigation.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py`
- [x] 1.2 Add diagnostic stop fields and `stop_reason` to `InvestigationStopped` (`refine_investigation.py`) and wire `stopped.stop_reason` into `refine.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/`

## 2. Documents

- [x] 2.1 Verify OpenSpec and docs checks pass
  - Verification: `$ uv run devops openspec check && uv run devops ci docs`
