# Design

## One file for one client

Kilo Code uses its own schema (`mcp`, `type: local`, array `command`, `environment`), so it cannot share `.mcp.json`. A template of its own keeps the server the same as the other templates: a test compares the command and the variables with the Claude template.

## Rejected alternatives

- **A `KILO.md` pointer stub**: rejected. Kilo Code reads `AGENTS.md` natively, so a stub is dead text.
- **`.kilo/kilo.jsonc`**: rejected. `.gitignore` excludes `.kilo/`, so the file would not reach a clone.
- **Reading `.mcp.json`**: rejected. Kilo Code does not read it.

## Test

`tests/test_devcontainer.py` renders the template, runs `init` and `post-start`, and reads the committed `kilo.jsonc`.
