# Tasks

## 1. Refuse GH_TELEMETRY_ENDPOINT_URL caller override

Reads: none. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`, `tests/core/test_subprocess_env_telemetry.py`.

- [ ] 1.1 Write a test that build_subprocess_env raises SecurityError when env contains GH_TELEMETRY_ENDPOINT_URL set to https://example.com. Write a test that build_subprocess_env does not raise SecurityError when env contains GH_TELEMETRY set to log, and the key is present in the returned dict. Write a test that build_subprocess_env does not raise SecurityError when env contains GH_TELEMETRY_SAMPLE_RATE set to 0.5, and the key is present. Write a test that with isolate_env=True and os.environ containing GH_TELEMETRY_ENDPOINT_URL, the key is absent from the returned dict, and verify that `uv run devops ci test tests/core/test_subprocess_env_telemetry.py` fails on the base
- [ ] 1.2 Add CONST_DATA_EGRESS_ENV_VARS: Final[frozenset[str]] = frozenset({"GH_TELEMETRY_ENDPOINT_URL"}) to src/devops_cli/config/constants.py. Import CONST_DATA_EGRESS_ENV_VARS in src/devops_cli/core/process.py. Extend _is_env_override_refused to return True when key.upper() is in CONST_DATA_EGRESS_ENV_VARS, in addition to the existing CONST_CODE_LOADING_ENV_PATTERNS check, and verify that `uv run devops ci test tests/core/test_subprocess_env_telemetry.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
