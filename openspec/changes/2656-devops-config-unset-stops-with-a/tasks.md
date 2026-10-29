# Tasks

## 1. Detect merge-derived key in _find and raise ConfigurationError

Reads: None.. Changes: None..

- [ ] 1.1 Write a test in tests/test_round_trip.py that builds a YAML text with a merge key (a: {b: &d {api_key: FAKE}}, ai: {<<: *d}), calls find(text, 'ai.api_key', name='config.yaml'), and asserts ConfigurationError is raised with a message that names config.yaml and mentions merge key. Also write a test that calls find with a directly-present key and asserts it returns the expected path and line., and verify that `uv run devops ci test tests/test_round_trip.py` fails on the base
- [ ] 1.2 In src/devops_cli/config/round_trip.py, add a name: str parameter to _find. After the if dotted in node: check, assign position = node.lc.key(dotted). If position is None, raise ConfigurationError with a message that names the file and states the key comes from a YAML merge key. Otherwise return the path and line as before. Update the recursive call to pass name. Update the call from find to pass name., and verify that `uv run devops ci test tests/test_round_trip.py` passes
- [ ] 1.3 No document change is needed. The module docstring already describes the find function's purpose., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
