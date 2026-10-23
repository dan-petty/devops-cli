# Task: Generate a GEMINI.md Pointer Stub (#1845)

**Issue**: [#1845](https://github.com/dan-petty/devops-cli/issues/1845)
**Scope**: type/feature
**Feasibility**: Checked on 2026-10-22 against Gemini CLI v0.65.0, the latest release. The documentation of the tag `v0.65.0` and of the main branch states the import syntax as `@file.md`. It shows only the forms `@./file.md`, `@../file.md` and `@/absolute/path/to/file.md`. The stub uses the documented form `@./AGENTS.md`, and the source of the tag also accepts the bare form. No agent started Gemini CLI, because the container has no binary and no Google account. A committed `.gemini/settings.json` works only in a trusted workspace, so the stub stays. The section "Evidence" gives the details.

## Description

Gemini CLI loads `GEMINI.md` by default. It reads `AGENTS.md` only when `context.fileName` names it. A session in a fresh clone did not see the rules of `AGENTS.md`. Claude Code and Copilot already had a pointer stub. This change adds the third stub with the existing generator and builds no new tool.

- **The table.** `POINTER_STUBS` in `src/devops_cli/ai/instruction_generator.py` maps a stub file name to a `PointerStub` row. The row holds the title, the tool name, the link to `AGENTS.md` and the import line, which is `None` for a tool that expands no import. The Claude Code row holds `@AGENTS.md`, the form that the Claude Code documentation shows. The Gemini CLI row holds `@./AGENTS.md`, the form that the Gemini CLI documentation shows. `generate_instruction_content` reads the row. `generate_pointer_stub` takes the keyword `import_line`. A leading `./` in the file name still selects the stub.
- **The deleted tests.** The change deletes the string test `target_file == CONST_CLAUDE_MD_FILENAME` and the test `"copilot" in target_file`. It also deletes the test `filename == CONST_CLAUDE_MD_FILENAME` in `generate_pointer_stub`.
- **The constant and the default list.** `CONST_GEMINI_MD_FILENAME` is new. `DEFAULT_AGENT_FILES` gets the entry "Pointer stub redirecting Gemini CLI to AGENTS.md".
- **One file table.** The change deletes the copy `_AGENT_FILES` in `src/devops_cli/commands/ai.py`. The `agents` command reads `DEFAULT_AGENT_FILES` for its default file list and its `show_default` text.
- **The stub.** `GEMINI.md` at the root is the output of `uv run devops ai agents --file GEMINI.md`. It has the `@./AGENTS.md` line, the pointer note and the pre-1.0 alpha notice, like `CLAUDE.md`.
- **The canonical-source note.** The note in `AGENTS.md` names `GEMINI.md` beside `CLAUDE.md` and `.github/copilot-instructions.md`. The note in the `AGENTS.md` template of the generator does the same. The test `test_agents_md_stays_within_character_budget` guards the cap of `AGENTS.md`.
- **The inventory.** `GEMINI.md` is in class `generated` of `CONST_DOCS_INVENTORY`, beside `CLAUDE.md`. `GEMINI.md` is in `[tool.mutmut] also_copy` of `pyproject.toml`, because a test reads it from the root of the checkout.
- **The text.** The docstring and the help text of the `agents` command name `GEMINI.md`. The generated CLI reference, `docs/commands/ai.md` and the README matrix carry the new docstring.
- **The pages.** The knowledge base pages on the scaffolding, the devcontainer lifecycle and agentic reviews name the third stub. The knowledge base index does the same. So do `docs/DEVCONTAINER_USAGE.md` and the comment in `src/devops_cli/commands/devcontainer.py`.

Source cost: the table replaces two branches of string tests and adds one row for each tool. The change deletes the second file table and adds no new module.

## Evidence

- **Version.** The latest release on npm was 0.65.0, published on 2026-10-20. The `package.json` of the tag says `0.65.0`.
- **Import syntax.** The pages are `docs/cli/gemini-md.md` and `docs/reference/memport.md`, and they read the same at the tag `v0.65.0` and on the main branch. The first page says: "by importing content from other files using the `@file.md` syntax." The second page says: "Use the `@` symbol followed by the path to the file you want to import:". It lists `@./file.md` (same directory), `@../file.md` (parent directory), `@./components/file.md` (subdirectory) and `@/absolute/path/to/file.md` (absolute path). The example `GEMINI.md` of the first page has the lines `@./components/instructions.md` and `@../shared/style-guide.md`.
- **Loading.** The default context file name is `GEMINI.md`. `packages/core/src/utils/memoryDiscovery.ts` calls `processImports` for each context file that it loads.
- **Both forms work, and the stub uses the documented one.** The documentation never shows a bare name such as `@AGENTS.md`, but it does not forbid one. The source of the tag accepts it. In `packages/core/src/utils/memoryImportProcessor.ts`, `findImports` takes an `@` at the start of the text or after white space. The path ends at the next white space and must start with `.`, `/` or a letter. The letter `A` passes. The project follows the documentation of the tool that reads the file, so the Gemini CLI row holds `@./AGENTS.md`. The documented form does not depend on that one rule of one version. The Claude Code row keeps `@AGENTS.md`, which the Claude Code documentation shows.
- **The limits of the import.** The processor resolves the path against the directory of the file that holds the import. It keeps the result inside the project root (the nearest `.git`). It follows at most 5 levels and skips text in backticks. The stub holds no other `@`.
- **The settings alternative.** The configuration documentation names `.gemini/settings.json` in the project root as the project settings file. The setting `context.fileName` takes a string or a list of strings and has no default. In `packages/cli/src/config/settings.ts`, `mergeSettings` drops the project settings when the workspace is not trusted (`isTrusted ? workspace : {}`). In `packages/core/src/tools/memoryTool.ts`, `setGeminiMdFilename` adds the names to the current list, so `GEMINI.md` stays in it.
- **The decision.** A committed settings file is not per-user, so the reason in the issue is incomplete. The file works only in a trusted workspace, and no generator writes it. The decision of ADR 0010 stands: one more stub from the existing generator, guarded byte for byte like the other two.
- **The file table in this tree.** `src/devops_cli/commands/ai.py` held a second copy of the file table, `_AGENT_FILES`. The issue does not mention it. `devops ai agents` read that copy, so a change to `DEFAULT_AGENT_FILES` alone would not have written `GEMINI.md`. A test of the command fails when the code reads a copy without Gemini.
- **The command run.** `uv run devops ai agents --file GEMINI.md` runs the stub path only and makes no model call. It wrote `GEMINI.md`.
- **What no agent ran.** No agent started Gemini CLI. The documentation and the source confirm the expansion, and a run does not. The first "Pending a person" bullet covers the run.

## Acceptance Criteria

- [x] `uv run devops ai agents` in this repository writes `GEMINI.md`. The committed file equals the output of the generator: `test_instruction_stubs_byte_equal_to_generator` and `test_ai_agents_command_scaffolds_instructions`.
- [x] `GEMINI.md` points to `AGENTS.md` and holds the `@./AGENTS.md` import line, and `CLAUDE.md` keeps `@AGENTS.md`: `test_generate_pointer_stub` and `test_instruction_content_for_each_pointer_stub_comes_from_its_table_row`.
- [x] The choice of a stub no longer branches on the file name in two places. One table decides the title, the tool, the link and the import line. A leading `./` still selects the stub: `test_instruction_content_for_a_stub_path_ignores_a_leading_dot_slash`.
- [x] `devops ai agents --file GEMINI.md` writes the stub alone and makes no model call: `test_ai_agents_file_option_writes_only_the_gemini_stub_without_a_model_call`.
- [x] A scaffold with no file list writes `GEMINI.md`. It skips an existing one without `--force`: `test_scaffold_agent_instructions` and `test_scaffold_agent_instructions_skips_an_existing_gemini_stub_without_force`. The devcontainer `init` and `post-create` tests also check that `GEMINI.md` is written.
- [x] The canonical-source note of `AGENTS.md`, and of the generated `AGENTS.md`, links every stub of `POINTER_STUBS`. `AGENTS.md` stays under its cap: `test_the_canonical_source_note_links_every_pointer_stub` and `test_agents_md_stays_within_character_budget`.
- [x] The inventory lists `GEMINI.md` as generated, and `devops docs check` passes: `test_the_generated_class_is_what_the_generator_writes`.
- [x] Seven changes to the code each make a named test fail, and a restore of the code makes it pass again. The changes remove the import line of the Gemini row, give the Gemini row the bare form `@AGENTS.md`, drop the Gemini entry of `DEFAULT_AGENT_FILES`, drop the `./` handling, drop Gemini from the file table of `commands/ai.py`, drop `GEMINI.md` from the inventory and drop the `GEMINI.md` link from the canonical-source notes.
- [x] `changelog.d/1845.md` records the change. `CHANGELOG.md` and `docs/ROADMAP.md` stay as they are.
- Pending a person: in a fresh clone, start Gemini CLI v0.65.0 or later with your own account and run `/memory show`. Check that the text of `AGENTS.md` is in the context. If it is not, file a defect that names the version.
- Pending a person: repeat the `/memory show` check in a folder that Gemini CLI does not trust. Report whether the project `GEMINI.md` loads there. The source check covered the settings file and not this case.
- Pending a person: say whether a committed `.gemini/settings.json` with `context.fileName` should replace this stub. The section "Evidence" shows that it works only in a trusted workspace.

## Deliverables

- [x] `src/devops_cli/ai/instruction_generator.py`: `CONST_GEMINI_MD_FILENAME`, the `DEFAULT_AGENT_FILES` entry, `PointerStub` and `POINTER_STUBS`, the `import_line` field and keyword, the note of the `AGENTS.md` template and the docstrings.
- [x] `src/devops_cli/commands/ai.py`: the deleted `_AGENT_FILES`, the use of `DEFAULT_AGENT_FILES` and the docstring of `agents`. `src/devops_cli/lang/en/help.py` and `src/devops_cli/commands/devcontainer.py`: the text.
- [x] `GEMINI.md`, and the note in `AGENTS.md`. `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`: the import line of the Gemini stub.
- [x] `src/devops_cli/config/constants.py`: `GEMINI.md` in class `generated`. `pyproject.toml`: `GEMINI.md` in `[tool.mutmut] also_copy`.
- [x] `tests/test_instruction_generator.py`, `tests/test_agents_md_claims.py` and `tests/test_docs_inventory.py`.
- [x] The knowledge base pages, `docs/DEVCONTAINER_USAGE.md`, and the generated `docs/CLI_REFERENCE.md`, `docs/commands/ai.md` and `README.md` matrix.
- [x] `changelog.d/1845.md`.
