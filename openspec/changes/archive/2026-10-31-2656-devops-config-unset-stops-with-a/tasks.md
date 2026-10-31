# Tasks

## 1. Add merge-key error in _find

Reads: None.. Changes: None..

- [x] 1.1 Write a test in tests/test_round_trip.py that creates a YAML text with a merge key (a: {b: &d {api_key: secret}} and ai: {<<: *d}), calls find(text, 'ai.api_key', name='config.yaml'), and asserts that a ConfigurationError is raised with a message containing 'config.yaml' and 'merge key'., and verify that `uv run devops ci test tests/test_round_trip.py` fails on the base
- [x] 1.2 In src/devops_cli/config/round_trip.py, add a name: str parameter to _find. In the branch where dotted in node is True, assign position = node.lc.key(dotted). If position is None, raise ConfigurationError(f'Cannot unset {name}: the key {dotted!r} comes from a YAML merge key.'). Otherwise return (*prefix, dotted), int(position[0]) + 1. Update the recursive call to pass name. Update find to pass name to _find., and verify that `uv run devops ci test tests/test_round_trip.py` passes
- [x] 1.3 No documentation change needed. The error message follows the existing ConfigurationError pattern in the module., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
