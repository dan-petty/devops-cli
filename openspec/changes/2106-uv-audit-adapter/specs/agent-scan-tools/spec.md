## ADDED Requirements

### Requirement: The uv audit tool runs the uv audit adapter over a directory
The agent tool `scan_uv_audit` and the MCP tool `scan_uv_audit` SHALL take only `directory`, a path inside the workspace, and SHALL run the uv audit adapter of `devops_cli.security` there. They SHALL keep no command line of their own, and SHALL reply as the other agent scan tools reply, with the scanner named `uv audit`.

#### Scenario: uv audit finds vulnerabilities
- **WHEN** an agent or an MCP client calls `scan_uv_audit` over a directory, and uv audit reports four vulnerabilities of idna 3.6
- **THEN** uv starts in that directory with `uv audit --frozen --quiet --output-format json`, and the reply is `uv audit scan status: ok`, then `Findings (4):`, then one line for each finding

#### Scenario: uv is not installed
- **WHEN** no directory of PATH holds uv, and the agent calls `scan_uv_audit`
- **THEN** the reply is `uv audit scan status: not installed`, then `Reason: Binary 'uv' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: The MCP tool takes only a directory
- **WHEN** an MCP client reads the input schema of `scan_uv_audit`
- **THEN** its only property is `directory`, with the default `.`
