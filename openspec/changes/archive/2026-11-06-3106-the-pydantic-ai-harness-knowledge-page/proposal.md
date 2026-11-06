# Proposal

## Why

The knowledge base page `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` names the archived repository `pydantic/pydantic-ai-harness` as the public source (#3106). That repository is frozen at v0.36.0, while the project pins version 0.59.0. An agent that reads the manual reads a stale source. This change points the manual to the maintained repository and path.

## What Changes

- The front matter `sources` of the harness manual lists `https://github.com/pydantic/pydantic-ai` instead of the archived repository URL.
- The 'Public Git Repository' row links to `https://github.com/pydantic/pydantic-ai` and names the path `src/pydantic_ai_harness` inside it.
- A test in `tests/ai/test_kb.py` asserts the front matter sources and the repository row link.
- A test in `tests/ai/test_kb.py` scans `kb_dir.rglob("*.md")` and asserts no manual in the knowledge base names `pydantic/pydantic-ai-harness`.
- The PyPI package keeps its name, so the pin `pydantic-ai-harness[coder]==0.59.0` in `pyproject.toml` stays unchanged.
- The knowledge base ingest reads local markdown files, so updating the page prevents ingest from indexing the archived URL.
- The change alters no consumer-observed behavior (documentation and tests only), so it sets `skip_specs: true` and adds no spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`
- Tests: `tests/ai/test_kb.py`

## Feasibility

- Upstream verification via `devops gh api repos/pydantic/pydantic-ai-harness` confirms the repository is archived (`"archived": true`, last push 2026-10-02).
- Upstream verification via `devops gh api repos/pydantic/pydantic-ai/contents/src/pydantic_ai_harness` confirms `src/pydantic_ai_harness` exists in the maintained `pydantic/pydantic-ai` repository with `pyproject.toml` and documentation.
- `search_code` for `pydantic/pydantic-ai-harness` on `origin/main` returned only lines 5 and 22 in `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`.
- `search_code` for `pydantic-ai-harness` returned `pyproject.toml:39: "pydantic-ai-harness[coder]==0.59.0"` and `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:3: - "pkg:pypi/pydantic-ai-harness@0.59.*"`. The pin and `applies_to` use the PyPI name and need no change.
- `read_file` on `.github/renovate.json` lines 34-37 shows `pep621` disabled: no Renovate rule matches `pydantic-ai-harness`. Dependency freshness runs via `devops ci outdated` in `.github/workflows/ci.yml:526` ("Dependency Freshness").
- `file_symbols` on `src/devops_cli/ai/kb.py` showed `get_knowledge_base_dir()` and `parse_manual_front_matter()`.
- `file_symbols` on `tests/ai/test_kb.py` showed `test_kb_front_matter_sources_validation()`, so tests already validate manual front matter.
- First check against the real system: `! git grep -n "pydantic/pydantic-ai-harness" src/devops_cli/ai/knowledge_base/` passes after the edit.
- Second check against the real system: `uv run devops ci test tests/ai/test_kb.py` runs the new tests.

## Existing Tool Considered

None. The change edits one documentation page and adds tests in `tests/ai/test_kb.py`. No open tool or external library covers internal manual text. Cost to implement: about 5,000 tokens to build, about 1,000 tokens per quarter to maintain and fix, and about 15 minutes of elapsed time; it deletes no internal code.
