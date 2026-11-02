## ADDED Requirements

### Requirement: The context lists the tests and the callers of a cited symbol
The context that the stage job and the refine job give the model SHALL hold, for each identifier the item cites in backticks, up to five of them, the Python files at the checked-out commit that name the identifier as a whole word. It SHALL list the test files first and the caller files after them. A test file is a file under `tests/` or a file named `test_*.py` or `*_test.py`. Every other file is a caller. An identifier that no file names SHALL add no section.

#### Scenario: A cited symbol is named by tests and by source files
- **WHEN** an item cites `hello_world`, and `tests/test_sample.py`, `pkg/test_inline.py` and `pkg/inline_test.py` name it, and `src/caller.py`, `src/contest.py` and `src/sample.py` name it
- **THEN** the context holds the section "Tests and callers of `hello_world`", the three test files under "Tests:" and the three source files under "Callers:"

#### Scenario: A cited symbol that no file names
- **WHEN** an item cites `missing_symbol` and no Python file names it
- **THEN** the context holds no section "Tests and callers"

### Requirement: The paths of one symbol are bounded
The context SHALL list at most `CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL` paths for one cited identifier, 50 paths, and SHALL list the tests before the callers when the list is cut. When it cuts the list, the context SHALL say how many paths it shows, how many files name the identifier, and how many it leaves out.

#### Scenario: More files name a symbol than the bound
- **WHEN** the bound is 3, and five test files and one source file name the cited identifier `hello_world`
- **THEN** the section of `hello_world` lists three test files and no caller, and ends with the line "(3 of 6 paths shown; 3 more left out)"

### Requirement: The context names the requirements of the specs that cover a cited file
The context SHALL hold, for each base spec of `openspec/specs/` that covers a cited file, up to five specs and up to 40 requirement names for each, the names of its `### Requirement:` headings, in the order of the spec. A spec covers a file when the file is a module of `src/devops_cli` and the name of the spec is the name of the package and the module joined with hyphens, or is the start of that name up to a hyphen, or when the text of the spec names the path of the file. A spec that covers no cited file SHALL add no section.

#### Scenario: A cited module has a spec of its name
- **WHEN** an item cites `src/devops_cli/widget/render.py`, and `openspec/specs/widget-render/spec.md` holds two requirements, and `openspec/specs/widget/spec.md` holds one, and `openspec/specs/other/spec.md` holds one
- **THEN** the context holds the section "Requirements of widget-render" with both names, and the section "Requirements of widget" with its name, and no name from `other`

#### Scenario: A spec names the path of a cited file
- **WHEN** an item cites `src/devops_cli/widget/render.py`, and the text of `openspec/specs/named-by-path/spec.md` names that path
- **THEN** the context holds the section "Requirements of named-by-path" with the requirement names of that spec

#### Scenario: No spec covers the cited file
- **WHEN** an item cites `src/sample.py` and no spec covers it
- **THEN** the context holds no section "Requirements of"

### Requirement: The new sections come before the cited code and stay inside the budget
The context SHALL put the sections of tests and callers and of requirement names before the cited code, so the cut of the token budget, which takes the end first, keeps them. The whole context SHALL stay inside the token budget that the job gives it.

#### Scenario: The sections come before the code
- **WHEN** an item cites `src/devops_cli/widget/render.py` and the spec `widget-render` covers it
- **THEN** the section "Requirements of widget-render" is before the section "Code: src/devops_cli/widget/render.py"

#### Scenario: A small budget
- **WHEN** forty test files name a cited identifier and the budget is 120 tokens
- **THEN** the context holds at most 120 tokens
