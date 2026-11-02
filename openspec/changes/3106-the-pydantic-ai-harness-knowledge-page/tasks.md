# Tasks

## 1. Point the harness manual at the maintained repository

Reads: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai.md`. Changes: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`.

- [ ] 1.1 In `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`, replace the front matter source `https://github.com/pydantic/pydantic-ai-harness` with `https://github.com/pydantic/pydantic-ai`. In the 'Public Git Repository' row of section 1, link to `https://github.com/pydantic/pydantic-ai` and write `github.com/pydantic/pydantic-ai` as the link text, then name the path src/pydantic_ai_harness as the place the harness code lives. Keep `applies_to`, `reviewed` and `tags` as they are, and keep the PyPI name `pydantic-ai-harness` where the page names the package, and verify that `! git grep -n "pydantic/pydantic-ai-harness" src/devops_cli/ai/knowledge_base/` passes

## 2. Assert the source of the harness manual in the knowledge base tests

Reads: `src/devops_cli/ai/kb.py`, `tests/ai/test_kb.py`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`. Changes: `tests/ai/test_kb.py`.

- [ ] 2.1 Add a test to `tests/ai/test_kb.py` that reads `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` through `get_knowledge_base_dir()` and `parse_manual_front_matter`: the front matter `sources` holds `https://github.com/pydantic/pydantic-ai` and no harness repository URL, and the 'Public Git Repository' row links to `https://github.com/pydantic/pydantic-ai` and names src/pydantic_ai_harness. Add a second test that reads each `*.md` file of `src/devops_cli/ai/knowledge_base/devops_cli/libraries/` and asserts none holds the text `pydantic/pydantic-ai-harness`, and verify that `uv run devops ci test tests/ai/test_kb.py` passes

## Criteria

- The knowledge page's front matter `sources` SHALL list `https://github.com/pydantic/pydantic-ai` and SHALL NOT list `https://github.com/pydantic/pydantic-ai-harness`.: group 1
- The 'Public Git Repository' row SHALL link to `https://github.com/pydantic/pydantic-ai` and name the path `src/pydantic_ai_harness`.: group 1
- The repository SHALL contain no reference to `pydantic/pydantic-ai-harness`.: group 2
- The lockfile SHALL still install `pydantic-ai-harness[coder]==0.59.0`.: pending-person, Only a full `uv sync --locked` on a real machine resolves and installs the package from PyPI; the change touches neither `pyproject.toml` nor the lockfile, so a person runs the check after the merge.
- The dependency update configuration SHALL still match the PyPI package `pydantic-ai-harness`.: pending-person, Only a Renovate run against the repository shows that the existing rule still finds the package; the change adds no rule and edits no configuration, so a person confirms the rule by hand.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
