# Tasks

## 1. Inventory reader and command

Reads: `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/tools_lock/__init__.py`, `src/devops_cli/commands/survey.py`. Changes: `src/devops_cli/research/`, `src/devops_cli/commands/research.py`, `src/devops_cli/exceptions/research.py`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/main.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/`, `tests/research/`, `tests/commands/test_research_inventory.py`, `tests/fixtures/research/repo/`.

- [x] 1.1 Add the fixture repository, with one pin of each kind and the same action at two versions, and the tests of the list, the order, the unknown count, the refusal of programs and sockets, the parse error and the real tree
  - Verification: `uv run devops ci test tests/research/test_inventory.py`
- [x] 1.2 Add `devops_cli.research` (the model, one reader for each format and `read_inventory`) and `InventoryError`
  - Verification: `uv run devops ci test tests/research`
- [x] 1.3 Add the group `devops research` with the command `inventory`, its dry-run class, its MCP tool and its tests
  - Verification: `uv run devops ci test tests/commands/test_research_inventory.py`
- [x] 1.4 Make the YAML helpers of `devops_cli.k8s.image_pins` public and add `key_line` and `image_nodes`
  - Verification: `uv run devops ci test tests/k8s`

## 2. Documentation

Reads: `README.md`. Changes: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md`, `docs/ERRORS.md`.

- [x] 2.1 Regenerate the command pages, the error table and the MCP tool list
  - Verification: `uv run devops docs generate --sync-readme`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
