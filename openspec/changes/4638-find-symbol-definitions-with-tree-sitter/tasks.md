# Tasks

## 1. Behavior: the definition lookup reads every source language

- [x] 1.1 Add the failing tests: a Rust function is defined on its `fn` line, a shell function on its line, a Rust call and a Markdown heading are no definition, a Python definition costs one command, and one command left leaves a name of another language undecided
  - Verification: `$ uv run devops ci test tests/roadmap/test_premise.py`
- [x] 1.2 Search the source files of `SYMBOL_PATHSPECS` with one `git grep -F -w`, pick the Python definitions with the Python expression, and confirm the other languages with `TreeSitterEngine` over one read in `src/devops_cli/roadmap/premise.py`; add `CONST_ROADMAP_DEFINITION_READ_FILES`
  - Verification: `$ uv run devops ci test tests/roadmap/test_premise.py`

- [x] 1.3 Add the failing test: 21 Rust files call a function that only a later file defines, and the lookup returns None; return None in `src/devops_cli/roadmap/premise.py` when the read leaves files out and finds no definition, and give `CONST_ROADMAP_DEFINITION_READ_FILES` and `CONST_ROADMAP_REFINE_DEFINITIONS_PER_SYMBOL` a class in `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. Behavior: the stage probe keeps its bound

- [x] 2.1 Add the failing tests: the probe confirms a Rust function, and with one command left it lists a Rust function as not probed
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`
- [x] 2.2 Pass the commands that are left to `definition_lines` in `src/devops_cli/roadmap/stage/stage_probe.py`, list an undecided identifier as not probed, search `SYMBOL_PATHSPECS` with `git log -S`, and keep the class field probe on `*.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`

- [x] 2.3 Add the test: the probe lists a function as not probed when the lookup leaves files out and finds no definition
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`

## 3. Behavior: the symbol section of the context names the definitions

- [x] 3.1 Add the failing test: a cited Rust function gets a section with its definition line, its test file and its caller
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py`
- [x] 3.2 Replace `SYMBOL_PATHSPEC` with `SYMBOL_PATHSPECS` in `src/devops_cli/roadmap/refine/refine.py`, and add the `Defined at:` line with at most `CONST_ROADMAP_REFINE_DEFINITIONS_PER_SYMBOL` definitions
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py tests/roadmap/test_premise.py tests/roadmap/stage/test_roadmap_stage_probe.py`

## 4. Documents

- [x] 4.1 Describe the definition of an identifier in other languages and the bound of its probe in `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
