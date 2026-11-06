## MODIFIED Requirements

### Requirement: The MCP Semgrep tool uses the default ruleset unless the caller names one
The MCP tool `scan_sast` SHALL scan with `DEFAULT_SEMGREP_CONFIG` when the caller names no config. It SHALL scan with the registry id that the caller names, as it is. It SHALL scan with the path that the caller names, resolved under the work tree of the server process, and it SHALL refuse a path outside that tree.

#### Scenario: The default ruleset and a named ruleset
- **WHEN** the cached `p/default` exists, and an MCP client calls `scan_sast` once with no config and once with the config `./rules`
- **THEN** the first Semgrep run names the cached file of `p/default` as its config, and the second run names the absolute path of `rules` under the work tree

#### Scenario: A named ruleset outside the work tree
- **WHEN** an MCP client calls `scan_sast` with the config `../../etc/passwd`
- **THEN** the tool raises a validation error that names `config`, and no Semgrep run starts
