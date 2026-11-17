# Proposal

## Why

The knowledge base holds 17 hand-typed files that describe this repository and drift from it: the settings table covers a fraction of the settings model, the coverage floor reads 90 against a real floor of 85, the board is said to own Status where ADR 0016 moved it to labels, and two files carry an old `httpx2` version (#3904). A digest built from the owner of each fact replaces those typed pages, so a model reads commands, settings, pins, architecture and decisions that match the code.

## What Changes

- Add `src/devops_cli/ai/project_digest.py`, which builds each section from its owner: `command_facts` over the command groups of the docs generator, `settings_sections` over the traversal of the settings model, `pin_facts` over the inventory readers, `architecture_facts` over the repository map and the import graph, and `decision_facts` over the decision records.
- Add `ProjectDigest` with the content hash and the commit, and `head_commit`, which reads the head commit through the process seam.
- Extract the traversal of the settings model out of `DocGenerator.generate_configuration_docs` into `iter_settings_fields` of `src/devops_cli/docs/generator.py`, so the page and the digest walk the model one time; the page keeps resolving the live default for its Default column and the digest reads the model's own default or the name of its default factory.
- Add the `project_digest` tool to `src/devops_cli/ai/tools/builtin_tools.py` and to `get_default_tools`, add the digest section to `generate_knowledge_base_index`, and regenerate `docs/KNOWLEDGE_BASE.md`.
- Rewrite the knowledge base fact pages to name the digest as the owner of each fact, remove the typed Purpose and Flags columns of the command reference page, and move each claim that no owner generates into `AGENTS.md`.
- Add `tests/ai/test_project_digest.py`, which asserts each section, the hash, the commit, the changed-lock case and the tool and index path offline.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `project-digest`: The digest lists every command and every settings section, Each pin comes from the file that owns it, The digest lists the repository map and the decision records, The digest carries its content hash and its commit, A model reads the digest through the tool and the index

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/project_digest.py`, `src/devops_cli/docs/generator.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/tools/registry.py`
- Documents: `docs/KNOWLEDGE_BASE.md`, `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`, `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, `AGENTS.md`
- Tests: `tests/ai/test_project_digest.py`

## Feasibility

- The probe "The path `uv.lock` is a file of the staging commit." confirms the uv lock at the root, which the pin section reads.
- The probe "The path `tools.lock` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/tools_lock/tools.lock`, `tests/fixtures/research/repo/src/devops_cli/tools_lock/tools.lock`. No commit in the history deleted or renamed it." shows where the tools lock sits; `search_code` for `LOCK_DIR = "src/devops_cli/tools_lock"` returned `src/devops_cli/research/tool_pins.py:18:LOCK_DIR = "src/devops_cli/tools_lock"`, and the plan creates no root file.
- The probe "The path `AGENTS.md` is a file of the staging commit." and the probe "The path `CONTRIBUTING.md` is a file of the staging commit." confirm the two documents that receive a claim with no owner.
- The probe `Not probed, the bound of 10 commands is reached` covers the rest of the paths that the issue cites, so the drift counts of the issue, the settings field map and the retrieval gold set are `not checked` in this run. The plan states no count for them and blocks on no gold set.
- `read_file` of `src/devops_cli/config/settings.py` lines 2366 to 2378 returned `src/devops_cli/config/settings.py:2372:class Settings(BaseSettings):`, the class whose fields group 1 projects, and the file defines that class once.
- The earlier finding on the settings default is answered: `read_file` of `src/devops_cli/docs/generator.py` lines 809 to 848 shows `src/devops_cli/docs/generator.py:812:section_val = getattr(settings, section_key, None)` and `src/devops_cli/docs/generator.py:840:getattr(section_val, field_name, None),`, so the Default column of the page holds a value resolved from a live settings object and not the model's own default. Group 1 therefore extracts only the traversal of the model into `iter_settings_fields`, `generate_configuration_docs` keeps its own resolution and its bytes, and `settings_sections` holds the model's own default or the name of its default factory, never a resolved value.
- `list_files` of `src/devops_cli/ai/knowledge_base/devops_cli` returned `architecture.md`, `cli_command_reference.md`, `configuration_and_settings.md`, `python_packages.md`, `libraries` and `tasks`, the hand-typed pages that the digest replaces.
- `search_code` for `generate_configuration_docs` returned `src/devops_cli/docs/generator.py:717:def generate_configuration_docs(self) -> str:`, and `read_file` of `src/devops_cli/docs/generator.py` lines 805 to 845 showed its walk over the fields of that class.
- `search_code` for `class DocGenerator:` returned `src/devops_cli/docs/generator.py:275:class DocGenerator:`, and `search_code` for `def introspect_all_groups` returned `src/devops_cli/docs/generator.py:418:def introspect_all_groups(self, force: bool = False) -> list[CommandGroupDoc]:`, the command owner that group 1 projects.
- `search_code` for `def generate_knowledge_base_index` returned `src/devops_cli/docs/generator.py:1253:def generate_knowledge_base_index(self) -> str:`, the index builder that group 5 extends.
- `search_code` for `if actual_content != expected_content:` returned `src/devops_cli/docs/generator.py:1420:if actual_content != expected_content:`, so `devops docs check` refuses a committed page that differs from its generator, and that is what group 6's verify runs.
- `search_code` for `get_check_spec("docs")` returned `src/devops_cli/commands/ci.py:2445:spec = get_check_spec("docs")` under `def docs(`, so `uv run devops ci docs` is the docs row that runs `devops docs check`.
- `search_code` for `cli_reference_lines` returned `tests/docs/test_docs_inventory.py:186:cli_reference_lines >= 60,`, so `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md` keeps at least 60 argv lines.
- `read_file` of `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md` showed `| Group | Subcommand | Purpose | Primary Flags / Arguments |` at line 9: `devops docs check` resolves the argv column only, and the Purpose and Flags columns are typed, so group 7 removes those two columns.
- `search_code` for `DEFAULT_REPOMAP_MAX_FILES` returned `src/devops_cli/config/defaults.py:629:DEFAULT_REPOMAP_MAX_FILES: int = 100`, so the digest passes `max_files` equal to the count of the Python modules under `src/` to `generate_repo_map`.
- `search_code` for `def read_inventory` returned `src/devops_cli/research/inventory.py:32:def read_inventory(root: Path) -> Inventory:`, whose components carry the file, the line, the name and the version of each pin, so the pin section names the file of each pin.
- `search_code` returned `src/devops_cli/core/import_graph.py:146:def build_import_graph(`, `src/devops_cli/ai/repomap.py:248:def generate_repo_map(`, `src/devops_cli/docs/adr_records.py:50:def read_record_texts(directory: Path) -> dict[str, str]:` and `src/devops_cli/roadmap/adr.py:181:def adr_of(path: str, text: str) -> Adr | None:`, the owners of the architecture and decision sections.
- `search_code` for `def get_default_tools` returned `src/devops_cli/ai/tools/registry.py:35:def get_default_tools() -> list[Any]:`, where the `project_digest` tool joins, and `file_symbols` of `src/devops_cli/ai/tools/builtin_tools.py` lists one plain function for each tool, so the new tool is one more function of that module.
- `list_files` of `src/devops_cli/ai` holds no `project_digest.py`, and `search_code` for `project_digest` and for `iter_settings_fields` returned no match, so group 1 creates both the module and the test module and each added name is new.
- The count of the commands, of the settings sections and of the mapped modules is unverified in this run, and the plan states no number for them; group 1's verify runs the census, because its test compares the digest with `introspect_all_groups` and `iter_settings_fields` rather than with a number, and the step stops when the two differ.
- Precondition of `build_project_digest(root, commit)`, `pin_facts(root)`, `architecture_facts(root)` and `decision_facts(directory)`: a checkout of the repository, because each reads the files under the root that it is given.
- Precondition of `head_commit(root)`: a checkout of the repository and a process, because it runs `git rev-parse HEAD` in it through `src/devops_cli/core/process.py:1153:def run_subprocess(`; no network.
- Precondition of the `project_digest` tool: a checkout of the repository, because it builds the digest of the current folder.
- Precondition of `src/devops_cli/docs/generator.py:class DocGenerator`, of its `introspect_all_groups` and of `generate_knowledge_base_index`: the installed package of devops-cli, because they introspect the live Typer tree and the bundled pages; no checkout, client or network.
- Precondition of `iter_settings_fields`, of `settings_sections` and of `generate_configuration_docs`: the settings model of `src/devops_cli/config/settings.py:class Settings`, which holds the fields that the digest lists; no checkout, client or network.
- `command_facts(groups)`, `digest_index_section(digest)`, `read_inventory`, `read_record_texts`, `adr_of`, `build_import_graph` and `generate_repo_map` need no checkout, client or network: they read the paths or the trees that they are given.
- Precondition of `check_docs` through `uv run devops ci docs`: a checkout of the repository, because it regenerates each page in memory and compares it with the committed file.
- The verifies are `uv run devops ci test <path>` and `uv run devops ci docs`. `uv`, `python`, `pytest`, `devops` and `git` are in the runner image, so no program of the plan is `NOT_IN_RUNNER`; a failing test is failure class `test`, and a page that differs from its generator is `lint`. The pod settings `readOnlyRootFilesystem: true` and `runAsNonRoot: true` hold, because each verify writes only the temporary folder of its test.
- The first checks against the real system are `uv run devops ci test tests/ai/test_project_digest.py`, `uv run devops docs generate` followed by `uv run devops ci docs`, and `uv run devops ci docs` for the rewritten pages.

## Existing Tool Considered

The repository already holds the command introspection of `src/devops_cli/docs/generator.py`, the settings model walk of `generate_configuration_docs`, the pin readers behind `read_inventory` of `src/devops_cli/research/inventory.py`, the repository map of `src/devops_cli/ai/repomap.py`, the import graph of `src/devops_cli/core/import_graph.py`, and the decision record readers of `src/devops_cli/docs/adr_records.py` and `src/devops_cli/roadmap/adr.py`. No open maintained tool covers a digest that joins the command tree, the settings model, the pins, the map and the records. The join is new code: 80k tokens to build, keep and fix it, and 4 hours of elapsed time.

## Dependencies

None.
