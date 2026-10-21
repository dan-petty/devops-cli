# Task: Writing and Checking Docs Consume a Generated Doc Set (#774)

**Issue**: [#774](https://github.com/dan-petty/devops-cli/issues/774)
**Scope**: scope/docs
**Feasibility**: Verified that `DocGenerator.generate_all_docs` already produced a canonical dictionary mapping relative file paths to their rendered contents (`dict[str, str]`). Integrating `"README.md"` into this returned doc set provides an end-to-end seam allowing `write_all_docs`, `check_docs`, and `sync_readme` to consume the pre-generated doc set directly, avoiding redundant command module imports and FastMCP introspection. Caching introspected command groups on the generator instance guarantees that `check_docs` introspects live command groups at most once.

| Metric | Before | After |
|---|---|---|
| `test_write_and_check_docs` & `test_doc_generator_write_all_and_check` execution | ~45s (7 full introspections + full argv passes) | ~2.3s (fixture doc set, zero introspection) |
| Live group introspection per `check_docs` call | 2 calls (`generate_all_docs` + `check_readme`) | 1 call (reused doc set / cached groups) |
| `devops docs generate` / `check` CLI output | Unchanged | Unchanged |

## Description

- [x] Refactored `DocGenerator.write_all_docs`, `check_docs`, and `sync_readme` in `src/devops_cli/docs/generator.py` to accept an optional `docs: dict[str, str] | None = None` parameter as the documentation seam.
- [x] Added `self._cached_groups` caching in `DocGenerator.introspect_all_groups` and included pre-rendered `"README.md"` into `generate_all_docs` output when root `README.md` exists.
- [x] Extracted static helpers `render_synced_readme` and `_check_readme_matrix_content` to keep McCabe complexity ($\le 5$) and indentation depth ($\le 3$) strictly within architectural invariants.
- [x] Updated `DocGenerator.check_docs` to skip full repository argv validation when running against a fixture doc set (`check_argv` defaults to `docs is None`), and reused the generated README content during README checks to ensure command groups are introspected only once.
- [x] Refactored mechanics tests in `tests/test_docs.py` (`test_write_and_check_docs` and `test_doc_generator_write_all_and_check`) to execute against a two-entry fixture doc set without module introspection or argv scanning.
- [x] Added `test_one_check_docs_call_introspects_once` in `tests/test_docs.py` verifying that a live `check_docs` call performs group introspection only once.
- [x] Verified `uv run devops docs check` and `uv run devops docs generate --check` pass with identical output.
- [x] Authored changelog fragment `changelog.d/774.md` under `### Changed`.
- [x] Verified full test suite and quality gates pass via `uv run devops ci`.
