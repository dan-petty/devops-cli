# Design

## Decisions

### 1. New leaf module `src/devops_cli/roadmap/markdown.py`
Create `src/devops_cli/roadmap/markdown.py` as a leaf module that imports only `functools` and `markdown_it`.
Define `commonmark_parser()` decorated with `@functools.cache`.
This avoids circular imports across roadmap modules.

### 2. Update plain CommonMark readers
Update the following plain readers to use `commonmark_parser()`:
- `src/devops_cli/roadmap/refine/refine.py`: `body_questions`, `body_dependencies`, and `_quoted_titles`.
- `src/devops_cli/roadmap/stage/stage_criteria.py`: `requirement_lines` and `acceptance_criteria`.
- `src/devops_cli/roadmap/step_files.py`: `step_files` uses `commonmark_parser()`.
Configured parsers with plugins or disabled rules retain their dedicated instances:
- `adr._RECORD_MARKDOWN` (`front_matter_plugin`)
- `body_hash._BODY_MARKDOWN` (`disable("inline")`)
- `refine._GITHUB_MARKDOWN` (`enable("table")`)
- `store._BODY_MARKDOWN` (`disable("inline")`)

### 3. Profile test with sys.setprofile
Verify parser construction count using `sys.setprofile` on `MarkdownIt.__init__.__code__`.
This tests the real constructor calls without patching devops-cli internal names.

## Rejected alternatives

### Put cached factory in store or refine
Rejected. `stores/store.py` and `refine/refine.py` are large modules.
Placing the factory there would cause import cycles across roadmap packages.

### Monkeypatch MarkdownIt in tests
Rejected. Project testing rules in `docs/TESTING.md` forbid monkeypatching internal objects.
Profiling with `sys.setprofile` tests real execution without test doubles.
