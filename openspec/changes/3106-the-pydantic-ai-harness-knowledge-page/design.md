# Design

## Decisions

- **Link the repository root https://github.com/pydantic/pydantic-ai and name src/pydantic_ai_harness as the path in the row text.**: The root URL stays valid regardless of the default branch name. The row text tells the reader where the harness source lives.
- **Change no dependency update configuration.**: `pyproject.toml:39` pins `pydantic-ai-harness[coder]==0.59.0`. `.github/renovate.json` disables Python package managers, and dependency freshness runs via scheduled CI.
- **Assert the page content in `tests/ai/test_kb.py`.**: That module tests the knowledge base and its front matter. A test that reads the page fails today on the archived URL.
- **Keep `applies_to`, `reviewed`, and `tags` of the front matter in their current form.**: `tests/review/test_kb_manuals_metadata.py` requires a non-empty `applies_to` and a `reviewed` date.
- **Omit spec deltas by setting `skip_specs: true`.**: The change modifies only internal documentation and tests, which alters no consumer-observed product behavior.

## Rejected alternatives

- **Link a tree URL that names the path.**: A tree URL assumes a default branch name that upstream could change.
- **Add a Renovate rule for the package.**: Python package managers are intentionally disabled in Renovate configuration.
- **Add a new test module under `tests/`.**: `tests/ai/test_kb.py` already reads the manuals and their front matter, so a second module would duplicate existing fixtures.
