# Proposal: #4482

## Why

Closes #4482. pydantic-ai makes the description of each tool from the docstring of its function, with griffe and the Google style. Three read tools had a `Returns:` section with a colon in the answer format: `callers` and `file_symbols` of the stage toolbox, and `search_code` of the refine investigation, which the stage toolbox gets from `InvestigationTools`. griffe reads a Google `Returns:` line as `type: description`, so it split the line at its first colon. Each stage and refine request thus showed the model a broken answer format, such as ``<type>One line for each match, as `path</type>`` and ``<description>line:content`.</description>``.

## What Changes

- The summary of each of the three docstrings holds the answer format, as `find_issues` already does, and the `Returns:` section goes. The tool description is then plain text, with the whole format, and the `<summary>` and `<returns>` tags go.
- One test builds the tool definitions of the stage toolbox and of the refine investigation, and asserts that each read tool description holds its answer format whole and that no description has a `<returns>` part.

The answer format of each tool does not change. The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a new requirement says that the description of each read tool shows its answer format whole.

## Impact

- `src/devops_cli/roadmap/stage/stage_tools.py`: the docstrings of `callers` and `file_symbols`.
- `src/devops_cli/roadmap/refine/refine_investigation.py`: the docstring of `search_code`.
- `tests/roadmap/stage/test_roadmap_stage_tools.py`: the new test.
- Every stage and refine request sends the three new descriptions. Each is a few tokens shorter, because the `<summary>` and `<returns>` tags go.
- No document quotes these docstrings, so no document changes.

## Feasibility

I confirmed the premise on 2026-11-11 with pydantic-ai 2.59.0 of `uv.lock`:

- The request capture of the context audit (item 3387, a stage plan run with a fake model through the real `plan_stage` path) holds the three broken descriptions. For example, `search_code` is ``<summary>Search the files of the repository for a text, in any case.</summary>\n<returns>\n<type>One line for each match, as `path</type>\n<description>line:content`.</description>\n</returns>``.
- The `tool_def.description` of each `Tool` that `StageTools(toolset="research").tools()` and `InvestigationTools(web=True).tools()` build gives the same text. After the change, the three descriptions are plain text that holds `path:line:content` and `line: signature` whole.
- A search of `src/` for a `Returns:` section with a colon in a code span finds only these three docstrings.

## Existing Tool Considered

pydantic-ai builds the description with griffe, and the fix uses its documented docstring form: a summary paragraph and an `Args:` section. The change adds no library and no helper. A `docstring_format` of `sphinx` or `numpy` on each `Tool` would parse the `Args:` sections wrongly. Cost: about 20,000 tokens to build, no upkeep, and about 1 hour of elapsed time.
