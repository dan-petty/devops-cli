# Proposal

## Why

The subprocess environment guard in build_subprocess_env accepts a caller override of GH_TELEMETRY_ENDPOINT_URL, which names the URL that gh sends its telemetry to. A caller can redirect gh telemetry to a host it names, which is egress of command data to an arbitrary destination. #2739

## What Changes

- Add CONST_DATA_EGRESS_ENV_VARS frozenset containing GH_TELEMETRY_ENDPOINT_URL to src/devops_cli/config/constants.py
- Import CONST_DATA_EGRESS_ENV_VARS in src/devops_cli/core/process.py
- Extend _is_env_override_refused to return True when the key is in CONST_DATA_EGRESS_ENV_VARS
- Add tests for the refusal, the ambient exclusion, and the acceptance of other GH_TELEMETRY keys
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: Refuse data-egress environment variable caller override, Ambient filter excludes data-egress keys, Non-egress GH_TELEMETRY keys remain accepted

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`
- Tests: `tests/test_process_env.py`

## Feasibility

- The premise is confirmed against the inputs: GH_TELEMETRY_ENDPOINT_URL is not in DEFAULT_ALLOWED_ENV_VARS (visible in src/devops_cli/core/process.py), not in DEFAULT_ALLOWED_ENV_PREFIXES, and _is_env_override_refused checks only CONST_CODE_LOADING_ENV_PATTERNS and CONST_GIT_ACCEPTED_ENV, so the key passes through the caller override path.
- First check: run the reproduction command uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(b(env={"GH_TELEMETRY_ENDPOINT_URL": "https://example.com"}))' to confirm the key is currently accepted without SecurityError.
- Second check: after the fix, run uv run devops ci test tests/test_process_env.py to confirm the key is refused and the other GH_TELEMETRY keys are accepted.

## Existing Tool Considered

No external tool covers this need. The change adds one key to the project's own refused-env-var list in src/devops_cli/config/constants.py and src/devops_cli/core/process.py. The written cost is about 15 lines of code and test, well under one page of tokens to build, keep and fix.
