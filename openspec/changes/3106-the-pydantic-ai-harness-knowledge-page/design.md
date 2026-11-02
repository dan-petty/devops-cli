# Design

## Decisions

- **Link the repository root https://github.com/pydantic/pydantic-ai and name src/pydantic_ai_harness as the path of the code in the row text.**: The root URL stays valid whatever the default branch is called, and the row text still tells a reader where the harness source lives.
- **Change no Renovate rule and no pin.**: `pyproject.toml:39` pins `pydantic-ai-harness[coder]==0.59.0` and the PyPI package keeps that name, so the existing rule still matches the package.
- **Assert the page content in `tests/ai/test_kb.py`.**: That module already tests the knowledge base that `src/devops_cli/ai/kb.py` loads and its front matter, and a test that reads the page fails today on the archived URL.
- **Keep `applies_to`, `reviewed` and `tags` of the front matter in their current form.**: `tests/review/test_kb_manuals_metadata.py` requires a non-empty `applies_to` and a `reviewed` date, and the pin and the review date do not change with the source URL.

## Rejected alternatives

- **Link a tree URL that names the path, such as https://github.com/pydantic/pydantic-ai/tree/main/src/pydantic_ai_harness.**: The page states no default branch of the maintained repository, so a tree URL would assume a branch name that no input confirms.
- **Add a Renovate rule for the new repository.**: `pyproject.toml:39` names the dependency as `pydantic-ai-harness[coder]==0.59.0`, which is a PyPI name, so the existing rule already matches it and a second rule adds nothing.
- **Add a new test module under `tests/` for the page.**: `tests/ai/test_kb.py` already reads the manuals and their front matter, so a second module would copy its fixtures and its imports for two assertions.
