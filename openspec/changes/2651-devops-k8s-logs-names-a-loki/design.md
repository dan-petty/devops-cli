# Design

## Decisions

- **Use loki.url as the config key name**: Matches the existing dot-separated pattern of qdrant.url, tempo.url, valkey.url and the text in the spec k8s-logs and the error message
- **The --loki-url flag overrides the setting**: Standard CLI convention: an explicit flag wins over a stored default. The existing code already gives the flag priority over the constant
- **The MCP tool k8s_logs reads the same setting**: The issue states the MCP tool SHALL use the configured address. The tool calls the same function as the CLI command, so one code change covers both
- **Default remains DEFAULT_LOKI_URL when loki.url is unset**: Preserves existing behavior for users who have not set the key. The constant is already defined in src/devops_cli/config/defaults.py

## Rejected alternatives

- **Use loki_url as the key name**: Does not match the dot-separated pattern used by every other service URL key: qdrant.url, tempo.url, valkey.url, pyroscope.url
- **Create a new file for the Loki config**: Adds a file for one key and breaks the single-file pattern of the config layer in src/devops_cli/config/settings.py
- **Leave the MCP tool on the constant only**: Contradicts the issue expected behavior and leaves the tool unable to reach a non-localhost Loki
