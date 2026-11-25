## Why

`roadmap alternatives` uses the repository SBOM and deployed file text in `Inventory` to turn an existing-tool match into `in-use`. When the LLM names a language's standard library repository such as `python/cpython`, neither the SBOM PURL (`pkg:pypi/...`) nor package links on `deps.dev` match `cpython` directly, so the verdict stays `covers` (issue #6347).

## Feasibility

Feasible in one pull request. Adding a static mapping of standard library GitHub projects to their SBOM PURL type and deployed file suffixes inside `src/devops_cli/roadmap/inventory.py` fits cleanly into the existing `Inventory.uses` flow with zero new external dependencies.

## Existing Tool Considered

No existing open tool in our dependency graph maps our SBOM PURL types and deployed file extensions to upstream standard library GitHub projects inside `Inventory.uses`. Adding this static mapping in `src/devops_cli/roadmap/inventory.py` costs ~60k tokens and ~2 hours, which avoids unnecessary `deps.dev` HTTP lookups and custom heuristic classifiers.

## What Changes

- Map standard library GitHub projects (`github.com/python/cpython`, `github.com/golang/go`, `github.com/rust-lang/rust`, `github.com/ruby/ruby`, `github.com/dotnet/runtime`, `github.com/nodejs/node`) to their SBOM PURL type and deployed file suffixes in `src/devops_cli/roadmap/inventory.py`.
- Collect deployed file suffixes in `_read_files` and store `suffixes: frozenset[str]` on `Inventory` (defaulting to `frozenset()` so existing 2-argument callers keep working).
- Check the standard library mapping in `Inventory.uses` against `self.packages` and `self.suffixes` before calling `_linked_packages(project)`.
- Update `docs/roadmap/alternatives.md` (`### The tools in use`) and add unit + end-to-end fake-model tests.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `roadmap-alternatives`: Mark a language's standard library as `in-use` when the repository SBOM holds a package of that ecosystem or its deployed paths include a file suffix of that language.

## Impact

- Code: `src/devops_cli/roadmap/inventory.py`
- Docs: `docs/roadmap/alternatives.md`
- Tests: `tests/roadmap/test_roadmap_alternatives_project_facts.py`, `tests/roadmap/test_roadmap_alternatives.py`
