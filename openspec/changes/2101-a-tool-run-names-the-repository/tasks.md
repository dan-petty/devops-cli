# Tasks

## 1. Add repository_uri to ToolRun and read it from git

Reads: none. Changes: `src/devops_cli/security/tool_executor.py`.

- [ ] 1.1 A test that creates a temporary git checkout with a remote URL containing user:password@, calls record_tool_run, and asserts ToolRun.repository_uri holds the URL without the userinfo. A second test creates a checkout with no remote and asserts repository_uri is None, and verify that `uv run devops ci test` fails on the base
- [ ] 1.2 Add repository_uri: str | None = None to the ToolRun model. Add a function _read_repository_uri(root: Path) -> str | None that calls _git(root, 'remote', 'get-url', 'origin', accepted=(0, 1)) and returns None on exit code 1. Strip the userinfo from the URL using urllib.parse.urlsplit and urlunsplit. Call _read_repository_uri in record_tool_run and pass the result to the ToolRun constructor. Update the module docstring to remove the note that the record holds no repository, and verify that `uv run devops ci test` passes

## 2. Write versionControlProvenance in the SARIF export

Reads: none. Changes: `src/devops_cli/security/sarif.py`.

- [ ] 2.1 A test that builds a SARIF document from a ToolRun with repository_uri set and a clean commit, and asserts the run object has versionControlProvenance with repositoryUri and revisionId. A second test uses a commit ending with -dirty and asserts versionControlProvenance is absent. A third test uses repository_uri None and asserts versionControlProvenance is absent, and verify that `uv run devops ci test` fails on the base
- [ ] 2.2 In the to_sarif function, for each run that has a ToolRun record, check if repository_uri is not None and commit is not None and commit does not end with -dirty. If all three hold, add a versionControlProvenance object with repositoryUri and revisionId to the run dictionary, and verify that `uv run devops ci test` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
