# Design

## Decisions

- **Render a built-in template set from a module beside the command, and edit the target files through that set.**: The project has few templates and needs offline runs. The scaffold must also insert a function into a Python module and an entry into the language folder, which Copier does not do.
- **Derive the MCP excluded set as every command of the tree that `CONST_MCP_EXPOSURE_TABLE` does not name, and keep the exposure table manual.**: Exposure over MCP is an explicit opt-in, and the command tree does not say which commands are safe to expose. A new command is then unexposed with no hand edit.
- **Make the hand-written class of `CONST_DOCS_INVENTORY` the complement of its other classes.**: A new hand-written page needs no inventory edit, and a file that no other class claims still lands in one class that the check reads.
- **State the mirror path as the one test-location rule in `docs/TESTING.md`.**: The stage gate of #3015 wants the mirror folder, and one rule removes the conflict that the issue records.
- **Put the group at `src/devops_cli/commands/new.py` as a top-level `devops new`.**: `src/devops_cli/main.py` registers the top-level groups in `_COMMAND_SPECS`, and no `dev` group exists.
- **Declare the dry-run class of each scaffold command with the `@dry_run_class` decorator on the command function.**: The ratchet `tests/invariants/test_dry_run_class_ratchet.py` reads the decorator of each command and its gaps file, so a decorator on the command keeps the group in the one place that the check reads.
- **Print only the manual steps that remain.**: A list that the change derives needs no edit, so a checklist entry for it would send the reader to a file that must stay as it is.
- **Write each template as text held in one module and render it with the paths that the command computes.**: The command computes every target path, so the path rule lives in one place and the refused case is checked before any write.

## Rejected alternatives

- **Copier or Cookiecutter as the template engine of the scaffold.**: Both render files and neither edits a command module, an entry of the language folder or a derived list. Copier's update mode also rewrites a file, against the no-overwrite rule of the issue.
- **Keep the hand-written MCP exclusion tuple in the coverage test.**: #3182: `roadmap eval verify` was absent from the tuple and Tests & Coverage failed, and the tuple now holds `("roadmap", "eval", "verify"),` as a hand patch.
- **Add a catch-all pattern for every page under the docs folder to the hand-written class.**: It hides a generated or prompt page that another class should own. The complement keeps the classes apart and still finds a page that no class matches.
- **Keep the flat-file fallback in the layout section of the test document.**: That fallback lets "a new flat file named after the behaviour", which contradicts the mirror target and the mirror rule that the stage gate enforces.
- **Put the scaffold under a `dev` group.**: `_COMMAND_SPECS` in `src/devops_cli/main.py` holds no `dev` group, so the nesting would add a level that nothing else uses.
- **Record the dry-run class of the new commands in a table of dry-run classes.**: No such table exists: the class of a command is the `@dry_run_class` decorator on its function, which `tests/invariants/test_dry_run_class_ratchet.py` reads beside its gaps file. A table would be a second record that no check reads.
