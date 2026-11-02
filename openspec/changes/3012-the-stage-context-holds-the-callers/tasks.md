# Tasks

## 1. List the tests and the callers of each cited symbol

Reads: `src/devops_cli/roadmap/refine.py` lines 575 to 800 (`collect_context` and its helpers), `tests/roadmap/test_roadmap_refine.py` lines 100 to 330 (the git fake and the `collect_context` tests), `src/devops_cli/config/constants.py` lines 2938 to 2965. Changes: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_refine.py`.

This group is `behavior`. It adds the section "Tests and callers of `<ident>`" to the context, and the bound of 50 paths for each symbol.

- [ ] 1.1 In `tests/roadmap/test_roadmap_refine.py`, make the git fake answer `git grep -l -z -F -e <needle>... <sha> -- <pathspec>`, and add the failing tests `test_a_cited_symbol_brings_its_tests_and_its_callers`, `test_a_symbol_with_no_other_file_adds_no_section` and `test_the_paths_of_one_symbol_are_bounded_and_the_cut_is_noted`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_refine.py -k "cited_symbol or bounded"` fails on the base
- [ ] 1.2 Add `CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL` to `config/constants.py`. Add `_grep_files`, `_is_test_path`, `_symbol_section` and `_collect_symbol_sections` to `refine.py`, and call the last from `collect_context`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_refine.py -k "collect_context or cited_symbol or bounded"` passes

## 2. Name the requirements of the specs that cover a cited file

Reads: `src/devops_cli/roadmap/refine.py` lines 575 to 800, `openspec/specs/roadmap-refine/spec.md` lines 1 to 30, `src/devops_cli/roadmap/stage.py` lines 752 to 758 (`capabilities_of`). Changes: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_refine.py`.

This group is `behavior`. It adds the section "Requirements of `<capability>`" to the context, before the cited code, and keeps the context inside its budget.

- [ ] 2.1 Add the failing tests `test_a_cited_file_brings_the_requirement_names_of_its_capability`, `test_a_cited_file_with_no_capability_adds_no_requirement_section` and `test_the_larger_context_stays_inside_the_token_budget`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_refine.py -k "requirement_names or no_capability"` fails on the base
- [ ] 2.2 Add `CONST_ROADMAP_REFINE_MAX_SPECS` and `CONST_ROADMAP_REFINE_MAX_REQUIREMENTS_PER_SPEC` to `config/constants.py`. Add `_module_capability_key`, `_capabilities_of_files`, `_requirements_section` and `_collect_spec_requirements` to `refine.py`, and put the two new kinds of section in `collect_context` before the cited code. Verify that `uv run devops ci test tests/roadmap/test_roadmap_refine.py -k "collect_context or cited or bounded or larger_context or capability"` passes

## 3. Keep the checks green and state the token cost

Reads: `design.md`. Changes: `design.md`, `proposal.md`.

This group is `other`. It has no test. The measure is in `design.md`; the repeatable check is the code of "To measure again" there.

- [ ] 3.1 Build the context for the body of #3012 before and after, count the added tokens, and write the table in `design.md`. Verify that `design.md` holds the table and the worst case
- [ ] 3.2 Verify that `uv run ruff check --config pyproject.toml src/devops_cli/roadmap/refine.py src/devops_cli/config/constants.py tests/roadmap/test_roadmap_refine.py`, `uv run mypy src/devops_cli/roadmap/refine.py` and `openspec validate --strict` pass

## Workflow follow-up

- A file list in each base spec would let the context name the requirements of any cited module, not only the 6 % that a name or a path covers. Pending a person: file an issue for it, and decide whether `devops openspec` or the planner owns the list.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
