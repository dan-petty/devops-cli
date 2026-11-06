# Design

## Context

See proposal.md for the scope (#3765, child F of #1330). The MCP seams exist already: `install_mcp_dispatcher` and `DispatcherFake` (#3760).

## Decisions

### 1. Each test moves as it is
- **Decision**: a script cut each test from the old file by its name and wrote it unchanged into the new file. Only the imports changed (ruff sorted them and removed the unused ones). Test classes became plain functions, and `self` left the signature.
- **Why**: a reviewer sees pure moves. The compare of the test names before and after proves that no test is lost.
- **Rejected**: rewrite the tests that still patch a `devops_cli` name. Child B (#3760) and #1336 own that work, and a rewrite in the same diff hides the moves.

### 2. Tests of `commands/mcp.py` go to `tests/commands/`
- **Decision**: the cases of `devops mcp serve`, `tools` and `export-schemas` move to two files of `tests/commands/`.
- **Why**: the test tree mirrors the source tree. The command lives in `src/devops_cli/commands/mcp.py`.
- **Rejected**: keep them in `tests/ai/mcp/`. That is the place of `ai/mcp/server.py`, not of the command.
- **Rejected**: add them to `tests/commands/test_mcp_serve.py`. That file has a module-wide keyring fixture and one subject, the remote transport.

### 3. The toolset tests get a mirror directory
- **Decision**: `tests/ai/toolsets/` is new, with an `__init__.py`. The one test that builds a `PydanticAgent` goes to `tests/ai/agents/test_agent_toolset_registration.py`.
- **Why**: `src/devops_cli/ai/toolsets/` had no test directory. The agent test is about `PydanticAgent`, which #2489 rewrites, so it sits with the agent tests.

### 4. Shared helpers: a support module and a conftest
- **Decision**: `call_tool` and `published_schemas` go to `tests/support/mcp_client.py` and lose their underscore. `handler_runner` and `fastmcp_log` go to `tests/ai/mcp/conftest.py`.
- **Why**: three new files use them. A test file must not import a private name from another test file.
- **Rejected**: copy the helpers into each file. That repeats 30 lines three times.
- **Rejected**: keep one big file for every test that uses them. That keeps the problem of this change.

### 5. The snapshot is one JSON file
- **Decision**: one test compares a dict keyed by tool name, with `description` and `input_schema`, with one `JSONSnapshotExtension` snapshot. It uses `run_middleware=False`, so the domain gate does not filter the listing.
- **Why**: syrupy sorts the keys, so a diff shows exactly the tool that changed. The file has 180 KB, and a split by domain would add files with no gain in a line diff.
- **Rejected**: the default amber `.ambr` format. Its text form is harder to read for a JSON schema.
- **Rejected**: add the annotations to the snapshot. The issue asks for name, description and input schema, and the registry tests already check the annotations.
