# Proposal

## Why

The knowledge base page `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` names the archived repository `pydantic/pydantic-ai-harness` as the public source. That repository is frozen at v0.36.0, so an agent that reads the page reads a source that does not match the pinned 0.59.0. Issue #3106 asks for the page to name the maintained repository and path.

## What Changes

- The front matter `sources` of the harness manual lists `https://github.com/pydantic/pydantic-ai` instead of the archived repository URL.
- The 'Public Git Repository' row links to `https://github.com/pydantic/pydantic-ai` and names the path src/pydantic_ai_harness inside it.
- A test asserts the sources and the repository row of the harness manual, and that no manual under the knowledge base names the archived repository.
- The pin `pydantic-ai-harness[coder]==0.59.0` and the Renovate rule that matches it stay unchanged, because the PyPI package keeps its name.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `knowledge-base-manual`: The harness manual names the maintained repository, No manual names the archived harness repository

### Modified Capabilities

None.

## Impact

- Documents: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`
- Tests: `tests/ai/test_kb.py`

## Feasibility

- The premise holds: `search_code` for `pydantic/pydantic-ai-harness` returned `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:5:  - "https://github.com/pydantic/pydantic-ai-harness"` and `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:22:| **Public Git Repository** | [github.com/pydantic/pydantic-ai-harness](https://github.com/pydantic/pydantic-ai-harness) |`. The page names the archived repository in both places that the issue cites.
- `search_code` for `pydantic-ai-harness` returned only those two lines of that page for the string with the `pydantic/` prefix, so the edit leaves the repository with no reference to the archived repository.
- `search_code` for `pydantic-ai-harness` also returned `pyproject.toml:39:    "pydantic-ai-harness[coder]==0.59.0",` and `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:3:  - "pkg:pypi/pydantic-ai-harness@0.59.*"`. The pin and the `applies_to` field use the PyPI name, which holds no `pydantic/` repository prefix, so they need no change.
- `file_symbols` on `src/devops_cli/ai/kb.py` returned `45: def get_knowledge_base_dir() -> Path:` and `242: def parse_manual_front_matter(content: str) -> tuple[KbFrontMatter | None, str, str | None]:`, so the test can read the page through the existing seams.
- `file_symbols` on `tests/ai/test_kb.py` returned `225: def test_kb_front_matter_sources_validation() -> None:`, so the module already reads the front matter of the manuals and the new test belongs there.
- First check against the real system: `git grep -n "pydantic/pydantic-ai-harness"` prints nothing and exits 1 after the edit.
- Second check against the real system: `uv run devops ci test tests/ai/test_kb.py` runs the new tests green.
- The repository is public, so the source URL of the page is public and no private address enters the change.

## Existing Tool Considered

None. The change edits one data page of the knowledge base and adds tests that read it, so no open, maintained tool or library covers it. Building the check costs about 5k tokens to write, near zero to keep and to fix, and minutes of elapsed time; it deletes no internal code.
