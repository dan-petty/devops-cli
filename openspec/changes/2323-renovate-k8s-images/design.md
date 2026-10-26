# Design

## Where the rule lives

`.github/renovate.json` holds the one pattern. The manager has no default pattern, so a pattern is the only way to enable it.

## Rejected alternatives

- **Pattern for single files** (`deployment.yaml` only): rejected. Images sit in `cronjob.yaml`, `valkey.yaml` and `ollama-profiles.yaml` too.
- **Group per namespace**: rejected for now. The issue gives the count of pull requests to a person, and a group can be added later with one rule.
- **Custom manager for `tools.lock`**: rejected. Each entry holds a `sha256` that a bump must change, and the hosted app runs no post-upgrade task.

## Test

`tests/test_renovate_config.py` reads the tracked files under `k8s/` and fails when a file that pins `image: name:tag` matches no pattern.
