# Design

## Decisions

- **Put the answer format in the summary.** griffe reads only a line that names a known section, such as `Returns:`, as the start of a section. A sentence in the summary paragraph stays text, with each colon in it. `find_issues` already gives its format this way ("each as `#N state title`").
- **Remove the `Returns:` sections.** The return type of each tool is `ToolReturn`, which the model does not see. The only use of the section was the answer format, and the summary now holds it.
- **One test for both toolboxes.** The stage toolbox gets `search_code` from `InvestigationTools`, so the test builds both toolboxes and reads each description as pydantic-ai sends it. The test also refuses a `<returns>` part in any description, so a new `Returns:` section shows in the test.

## Rejected alternatives

- **Set `docstring_format` on each `Tool`.** The `sphinx` and `numpy` styles do not read the Google `Args:` sections, so the parameter descriptions would go.
- **Escape the colon in the `Returns:` line.** griffe splits at the first colon of the line, and a Markdown escape would show in the description as a backslash.
- **Change the answer format.** Other work changes `read_file` and the trace gate. The format of the three tools stays.
