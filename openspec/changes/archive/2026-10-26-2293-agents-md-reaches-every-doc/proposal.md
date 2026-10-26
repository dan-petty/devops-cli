# Proposal

## Why

Issue #2293: `AGENTS.md` is the one router for every agent, and some documents that an agent needs have no route from it.

- Documents are routed by links. Following the inline Markdown links from `AGENTS.md`, 52 hand-written and generated documents of `CONST_DOCS_INVENTORY` are more than two links away: the settings, environment variable, error code and command references, the knowledge base catalog, the MCP tool list, the guides for the dev container and known issues, `tf/README.md`, `docs/agent/README.md`, `k8s/llm/profiles/README.md`, `README.md` itself, and the 40 pages of the command groups. The issue counted two documents by a looser reading that also took a path in backticks as a route.
- `AGENTS.md` has 6,452 of its 6,500 characters (`CONST_AGENTS_MD_MAX_CHARS`), so a row for each of these tasks does not fit.
- `tests/test_agents_md_claims.py` checks that each linked document exists, not that each document is linked.

## What Changes

- `README.md` is the hub for reference documents. It lists the settings, error code, telemetry, knowledge base, OpenTofu and agent record documents next to the references it already lists.
- `AGENTS.md` gets a row that sends "look up a setting, variable, error code, metric or command" to `README.md`, and the OpenTofu guide joins the cluster row. The link to ADR 0010 leaves the OpenSpec row, because the row for decisions already routes to `docs/adr/`. The word "thin" leaves the note on pointer files. The file has 6,498 characters, and the cap does not rise.
- The command matrix that `devops docs generate --sync-readme` writes into `README.md` links each command group to its page in `docs/commands/`.
- `k8s/README.md` links `k8s/llm/profiles/README.md`.
- A test walks the links from `AGENTS.md` and fails for a hand-written or generated document that is more than two links away, naming it.
- The change alters no command, option or message. It changes documents, the cell of a generated table, and tests, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `AGENTS.md`, `README.md`, `k8s/README.md`, and the generated pages (`README.md` matrix).
- Code: `src/devops_cli/docs/generator.py` (`render_readme_matrix`).
- Tests: `tests/test_agents_md_claims.py`, `tests/test_docs.py`.

## Feasibility

- The premise holds, and is larger than the issue says. A breadth-first walk over the inline Markdown links, the walk that the new test makes, finds 52 documents of the two classes that no chain of two links from `AGENTS.md` reaches on `main`.
- The cap is fixed by `CONST_AGENTS_MD_MAX_CHARS` and `test_agents_md_stays_within_character_budget`. A row for each task costs about 350 characters, and the file has 48 to spare, so the links go to `README.md`, which has no cap.
- `README.md` links the files that it lists, so one link from `AGENTS.md` to it brings `docs/DEVCONTAINER_USAGE.md`, `docs/KNOWN_ISSUES.md`, `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md` and `docs/ENV_VARS.md` within two links. A walk with the new links brings every document of both classes within two links.

## Existing Tool Considered

`markdown-it-py`, which the test module already uses to read links, covers the link walk. This change adds no library.
The change deletes the link to ADR 0010 and the word "thin" in `AGENTS.md`.
