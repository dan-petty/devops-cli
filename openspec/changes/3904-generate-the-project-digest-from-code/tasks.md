# Tasks

## 1. Build the command and settings sections from their owners

Kind: behavior. Reads: `src/devops_cli/docs/generator.py`, `src/devops_cli/config/settings.py`, `tests/docs/test_docs.py`, `tests/ai/agents/test_pydantic_ai_exceptions.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_cli_format_adoption.py`, `tests/docs/test_docs_adr_records.py`, `tests/docs/test_docs_inventory.py`, `tests/docs/test_docs_knowledge_base_argv.py`, `tests/docs/test_docs_source_argv_collector.py`, `tests/docs/test_docs_synced_blocks.py`, `tests/docs/test_exceptions.py`. Changes: `src/devops_cli/ai/project_digest.py` (new), `src/devops_cli/docs/generator.py`, `tests/ai/test_project_digest.py` (new).
Adds: `command_facts`, `settings_sections`, `iter_settings_fields`

- [x] 1.1 Add `test_command_facts_lists_each_registered_command_and_no_absent_one` to `tests/ai/test_project_digest.py`: it asserts that `command_facts` holds each group and command of `DocGenerator.introspect_all_groups` of `src/devops_cli/docs/generator.py`, that `settings_sections` holds each section and field of the model of `src/devops_cli/config/settings.py` with the model's own default or the name of its default factory, that no entry carries a resolved value, and that a command name that no module registers is absent
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py tests/docs/test_docs.py` fails on the base
- [x] 1.2 Write the failing test in `tests/ai/test_project_digest.py` first. Extract the traversal of the settings model's fields and of each section model out of `generate_configuration_docs` of `src/devops_cli/docs/generator.py` into a module-level `iter_settings_fields`, which yields the section key, the section model, the field name and the `FieldInfo` and resolves no value. `generate_configuration_docs` keeps its own live settings object and its `getattr` reads for the Default column, so the page keeps its bytes. Add `command_facts(groups)` and `settings_sections()` to `src/devops_cli/ai/project_digest.py`: the first turns the `CommandGroupDoc` list of `introspect_all_groups` into one entry for each group and command with the group name, the command name and the help text, and the second projects `iter_settings_fields` into each section's name and each field's dotted name, annotation and model default or default-factory name, never a resolved value
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py tests/docs/test_docs.py` passes

## 2. Read each pin from the file that owns it

Kind: behavior. Reads: `src/devops_cli/research/inventory.py`, `src/devops_cli/research/python_pins.py`, `src/devops_cli/research/node_pins.py`, `uv.lock`, `pyproject.toml`, `package-lock.json`, `src/devops_cli/ai/project_digest.py`. Changes: `src/devops_cli/ai/project_digest.py`, `tests/ai/test_project_digest.py`.
Adds: `pin_facts`

- [x] 2.1 Add `test_each_pin_equals_its_lock_and_a_changed_lock_changes_the_pin_section` to `tests/ai/test_project_digest.py`: it asserts that each pin of `pin_facts` equals the version of the same name in `uv.lock`, and that a temporary root holding copies of `pyproject.toml` and `uv.lock` with one version changed gives that version with `uv.lock` as its file
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py` fails on the base
- [x] 2.2 Write the failing test first. Add `pin_facts(root)` to `src/devops_cli/ai/project_digest.py`, which calls `read_inventory(root)` of `src/devops_cli/research/inventory.py` and returns one entry for each component with its name, its version and the file that holds it. The readers of `src/devops_cli/research/python_pins.py` and `src/devops_cli/research/node_pins.py` return an empty list for a file that the root does not hold, so the temporary root needs the two copied files only
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py` passes

## 3. Add the repository map, the import graph and the decision records

Kind: behavior. Reads: `src/devops_cli/ai/repomap.py`, `src/devops_cli/core/import_graph.py`, `src/devops_cli/docs/adr_records.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/ai/project_digest.py`. Changes: `src/devops_cli/ai/project_digest.py`, `tests/ai/test_project_digest.py`.
Adds: `architecture_facts`, `decision_facts`

- [x] 3.1 Add `test_the_digest_lists_each_module_each_import_edge_and_each_decision_record` to `tests/ai/test_project_digest.py`: it asserts that the module paths of `architecture_facts` equal the paths of `generate_repo_map`, that each edge names two modules of `build_import_graph`, and that each record of `docs/adr` appears in `decision_facts` with its title and its status
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py` fails on the base
- [x] 3.2 Write the failing test first. Add `architecture_facts(root)` to `src/devops_cli/ai/project_digest.py`, which parses each Python module under `src/` with `ast.parse`, calls `build_import_graph` of `src/devops_cli/core/import_graph.py` for the edges, and takes the module paths and symbol counts from `generate_repo_map(root, max_files=<the count of those modules>)` of `src/devops_cli/ai/repomap.py`. Add `decision_facts(directory)`, which reads each record with `read_record_texts` of `src/devops_cli/docs/adr_records.py` and takes its title and status from `adr_of` of `src/devops_cli/roadmap/adr.py`
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py` passes

## 4. Assemble the digest with its content hash and its commit

Kind: behavior. Reads: `src/devops_cli/core/process.py`, `src/devops_cli/ai/project_digest.py`, `uv.lock`. Changes: `src/devops_cli/ai/project_digest.py`, `tests/ai/test_project_digest.py`.
Adds: `ProjectDigest`, `build_project_digest`, `head_commit`

- [x] 4.1 Add `test_the_digest_hashes_its_sections_and_names_the_commit_it_was_given` to `tests/ai/test_project_digest.py`: it asserts that two builds of one section map give one hash, that a changed section gives another hash, that a temporary root with a changed `uv.lock` gives another hash again, and that `head_commit` returns the SHA that the doubled `run_subprocess` call answers
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py` fails on the base
- [x] 4.2 Write the failing test first. Add `ProjectDigest` with the five sections, the content hash and the commit, and `build_project_digest(root, commit)`, which fills the sections from the functions of groups 1 to 3 and hashes their canonical JSON with `hashlib.sha256`. Add `head_commit(root)`, which asks `run_subprocess` of `src/devops_cli/core/process.py` for `git rev-parse HEAD`. The commit is an argument of the build, so the hash test doubles no process
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py` passes

## 5. Reach the digest through the tool and the knowledge base index

Kind: behavior. Reads: `src/devops_cli/ai/project_digest.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/tools/registry.py`, `src/devops_cli/docs/generator.py`, `tests/docs/test_docs.py`, `tests/ai/agents/test_pydantic_ai_exceptions.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, `tests/ai/review/test_review_security_tools.py`, `tests/ai/tools/test_persona_tools.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_cli_format_adoption.py`, `tests/docs/test_docs_adr_records.py`, `tests/docs/test_docs_inventory.py`, `tests/docs/test_docs_knowledge_base_argv.py`, `tests/docs/test_docs_source_argv_collector.py`, `tests/docs/test_docs_synced_blocks.py`, `tests/docs/test_exceptions.py`, `tests/security/test_builtin_tools.py`, `tests/security/test_security_gitleaks.py`, `tests/security/test_vulnerability_lookup.py`. Changes: `src/devops_cli/ai/project_digest.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/tools/registry.py`, `src/devops_cli/docs/generator.py`, `tests/ai/test_project_digest.py`.
Adds: `digest_index_section`, `project_digest`

- [x] 5.1 Add `test_the_project_digest_tool_and_the_index_section_name_the_same_sections` to `tests/ai/test_project_digest.py`: it asserts that the `project_digest` tool returns the content hash and the commit, and that the section of `generate_knowledge_base_index` names each section that the tool returns
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py tests/docs/test_docs.py` fails on the base
- [x] 5.2 Write the failing test first. Add `digest_index_section(digest)` to `src/devops_cli/ai/project_digest.py`, which renders the section names only. Add the `project_digest` tool to `src/devops_cli/ai/tools/builtin_tools.py` and to `get_default_tools` of `src/devops_cli/ai/tools/registry.py`; it builds the digest of the current folder and returns its sections, its content hash and its commit. Append the section in `generate_knowledge_base_index` of `src/devops_cli/docs/generator.py`
  - Verification: `$ uv run devops ci test tests/ai/test_project_digest.py tests/docs/test_docs.py` passes

## 6. Regenerate the knowledge base catalog page

Kind: other. Reads: `src/devops_cli/docs/generator.py`, `docs/KNOWLEDGE_BASE.md`. Changes: `docs/KNOWLEDGE_BASE.md`.

- [x] 6.1 Run `uv run devops docs generate` and commit the regenerated `docs/KNOWLEDGE_BASE.md` with its project digest section. Edit no generated page by hand
  - Verification: `$ uv run devops ci docs` passes
- [x] 6.2 Regenerate `docs/KNOWLEDGE_BASE.md` from its generator with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 7. Point the knowledge base fact pages at the digest

Kind: other. Reads: `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, `AGENTS.md`, `tests/docs/test_docs_inventory.py`. Changes: `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, `AGENTS.md`.

- [ ] 7.1 Remove each typed fact that the digest owns from `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md` and `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`: the settings table, the version table and the architecture narrative. Each page names the `project_digest` tool as the owner of the fact and keeps only the guidance that no owner generates. In `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, remove the typed Purpose and Primary Flags columns and keep the group and argv columns, so the page holds the argv lines that `devops docs check` resolves and at least the 60 lines that `tests/docs/test_docs_inventory.py:186:cli_reference_lines >= 60,` counts. Move each claim that no owner generates once into `AGENTS.md`, and list each move for the pull request comment
  - Verification: `$ uv run devops ci docs` passes
- [ ] 7.2 Rewrite `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md` and `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md` to name the digest as the owner of each fact, and add each unowned claim to `AGENTS.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: the digest contains every command and every settings section that exists, and a command that does not exist is absent.
- Group 2: A test: a version in the digest equals the version in `uv.lock` or `package-lock.json`; changing the lock file changes the digest.
- Group 4: The digest carries a content hash and the commit it was built from.
- Pending person: A claim that cannot be generated is moved once to `AGENTS.md`, `CONTRIBUTING.md` or an ADR, and the list of moved claims is in the pull request comment., Group 7 moves each claim that no owner generates into `AGENTS.md`, and the list of the moves goes in the pull request comment, which a person writes after the implementation.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
