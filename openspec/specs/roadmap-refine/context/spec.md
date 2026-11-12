# roadmap-refine/context Specification

## Purpose
The context that the stage and refine jobs give the model about cited code: the tests and the callers of a cited symbol, and the requirement names of the specs that cover a cited file.

## Requirements

### Requirement: The context lists the tests and the callers of a cited symbol
The context that the stage and refine jobs give the model SHALL hold, for up to five identifiers that the item cites in backticks, the source files of the checked-out commit that name each one as a whole word, Markdown files excepted. It SHALL name the file and line of up to three definitions, then the test files, then the callers. A test file is under `tests/` or named `test_*.py` or `*_test.py`; every other file is a caller. An identifier that no file names SHALL add no section.

#### Scenario: A cited symbol is named by tests and by source files
- **WHEN** an item cites `hello_world`, and `tests/test_sample.py`, `pkg/test_inline.py` and `pkg/inline_test.py` name it, and `src/caller.py`, `src/contest.py` and `src/sample.py` name it
- **THEN** the context holds the section "Tests and callers of `hello_world`", the three test files under "Tests:" and the three source files under "Callers:"

#### Scenario: A cited Rust function
- **WHEN** an item cites `explorer_patrol_system`, which `src/game/unit.rs` defines on line 5 and calls, and `tests/patrol.rs` calls it
- **THEN** the section of `explorer_patrol_system` holds "Defined at: src/game/unit.rs:5", `tests/patrol.rs` under "Tests:" and `src/game/unit.rs` under "Callers:"

#### Scenario: A cited symbol that no file names
- **WHEN** an item cites `missing_symbol` and no source file names it
- **THEN** the context holds no section "Tests and callers"

### Requirement: The paths of one symbol are bounded
The context SHALL list at most `CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL` paths for one cited identifier, 50 paths, and SHALL list the tests before the callers when the list is cut. When it cuts the list, the context SHALL say how many paths it shows, how many files name the identifier, and how many it leaves out.

#### Scenario: More files name a symbol than the bound
- **WHEN** the bound is 3, and five test files and one source file name the cited identifier `hello_world`
- **THEN** the section of `hello_world` lists three test files and no caller, and ends with the line "(3 of 6 paths shown; 3 more left out)"

### Requirement: The context names the requirements of the specs that cover a cited file
The context SHALL hold the names of the `### Requirement:` headings of each base spec in `openspec/specs/` that covers a cited file, in the order of the spec, for up to five specs and up to 40 names each. A spec covers a module of `src/devops_cli` when its name is the package and the module joined with hyphens, or the start of that name up to a hyphen. A spec also covers a file when its text names the path of the file. A spec that covers no cited file SHALL add no section.

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
