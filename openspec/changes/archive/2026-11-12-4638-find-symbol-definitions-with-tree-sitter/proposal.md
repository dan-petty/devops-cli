# Proposal: #4638

## Why
The definition lookup reads only Python. Closes #4638.

- `definition_lines` of `src/devops_cli/roadmap/premise.py` matches a Python `def`, `class` or assignment with one `git grep -E` over `*.py`.
- The stage probe and the implement premise check call it, so the probe says that a Rust function that a dreamscaper issue cites has no definition. That is false premise evidence.
- The refine and stage context lists the tests and callers of a cited symbol only from `*.py` files (`SYMBOL_PATHSPEC`), so a Rust symbol gets no section.

## What Changes
- `definition_lines` runs one `git grep -n -z -F -w` for the name over the source files of each language that `EXT_TO_LANG` maps, except Markdown. A Python line defines the name with the same expression as before, now applied in Python. When no Python line defines it, one more `git grep` reads the other files that name it, at most `CONST_ROADMAP_DEFINITION_READ_FILES` (20), and `TreeSitterEngine.parse_code` confirms a symbol of that name. The definition line is the first line in the span of the symbol that names it.
- `definition_lines` takes `commands`, the commands that the caller has left. When the other files need the read and one command is left, it returns None. The stage probe then lists the identifier as not probed, so the bound of 10 commands stays.
- `SYMBOL_PATHSPEC` becomes `SYMBOL_PATHSPECS`. The context section of a cited symbol lists the source files of all these languages and names up to `CONST_ROADMAP_REFINE_DEFINITIONS_PER_SYMBOL` (3) definitions as `Defined at: <path>:<line>`. The `git log -S` probe of an undefined identifier searches the same files. The class field probe stays on `*.py`.
- Test names, test selection and the stage test checks stay Python-only.

## Capabilities
- `roadmap-implement-job`: the shared definition lookup reads every source language.
- `roadmap-refine`: the symbol section lists the source files and the definitions.
- `roadmap-stage`: the probe lists an identifier that the bound leaves undecided as not probed.

## Impact
- `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/config/constants.py`, `docs/roadmap/stage.md`.
- A Python repository gets the same definition lines, and a lookup of a name that only Python files name still costs one command.
- The change fits one pull request.

## Feasibility
- The premise of the issue holds for the lookup and the refine section: `refine.py` sets `SYMBOL_PATHSPEC = "*.py"`, and `definition_lines` greps only that pathspec.
- The premise that the installed grammars give a `TAGS_QUERY` for each language fails. In the pinned grammar packages, `tree_sitter_bash`, `tree_sitter_hcl`, `tree_sitter_markdown`, `tree_sitter_dockerfile` and `tree_sitter_yaml` have no `TAGS_QUERY`, `tree_sitter_c_sharp.TAGS_QUERY` is None, and the TypeScript query holds only signatures, as it inherits the JavaScript query. So a tags query cannot find the shell function of the acceptance criteria. `TreeSitterEngine` already reads the symbols of all 14 grammars (a Rust `function_item`, a shell `function_definition`), and the stage agent tool `file_symbols` uses it, so the lookup uses it too.
- On a local checkout of dreamscaper, the new lookup gives `src/game/unit.rs:81:fn explorer_patrol_system(` for the function that dreamscaper issue #3 cites, and the base lookup gives no line.
- `git grep -n -z` prints `<sha>:<path>`, the line number and the text, separated by NUL, and `git grep -e ^` prints every line of a file, so one command reads all the files.

## Existing Tool Considered
- tree-sitter, through the `TreeSitterEngine` of `src/devops_cli/ai/ast/engine.py`, which the project already pins and uses. Tag queries were considered and rejected (see Feasibility). universal-ctags is not in the runner image and adds a program.
- The change deletes the `git grep -E` POSIX expression of `_definition_pattern`; the same expression now runs in Python over the lines of one search.
