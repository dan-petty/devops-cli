# Proposal

## Why

The SARIF export of a review writes no versionControlProvenance. SARIF 2.1.0 requires a repositoryUri in that object (section 3.23.3). The ToolRun record holds the commit but not the repository. A -dirty commit is not a valid revision of the scanned files (section 3.23.4). See #2101.

## What Changes

- Add repository_uri field to ToolRun, read from git remote get-url origin with credentials stripped
- Write versionControlProvenance in the SARIF export for clean commits that have a repository URI
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-runs`: ToolRun repository_uri field
- `sarif-export`: versionControlProvenance in SARIF export

## Impact

- Code: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/security/sarif.py`

## Feasibility

- The _git helper in src/devops_cli/security/tool_executor.py already runs git commands and handles errors, so git remote get-url origin fits the existing pattern.
- The ToolRun model is a Pydantic frozen model; adding a str | None field is a one-line change.
- The module docstring of src/devops_cli/security/tool_executor.py names the SARIF export as devops_cli.security.sarif.to_sarif, confirming src/devops_cli/security/sarif.py exists.
- The vendored schema at tests/fixtures/sarif-schema-2.1.0.json line 2941 lists repositoryUri as required in versionControlDetails.
- First checks: run git remote get-url origin in a test checkout to confirm it returns the expected URL; run the existing SARIF export tests to confirm they still pass after the change.

## Existing Tool Considered

No external tool covers this. The change extends the existing ToolRun record and SARIF export in src/devops_cli/security/. No internal code is deleted.
