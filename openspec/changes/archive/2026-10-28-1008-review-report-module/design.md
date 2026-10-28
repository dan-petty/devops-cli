# Design

## The input

`ReportInput` is a frozen, keyword-only dataclass. It holds what the report shows and nothing that the report has to fetch:

- the session: id, name, time of generation, the paths of review.md and findings.json;
- the findings: the reportable ones, all consolidated findings and the candidates, the dependencies, the network references, the symbol delta and the count of reviewed files;
- the run: the errored files, the partial-context and full-output flags, the analyzer line of the executive summary, each analyzer's state and note, the coverage matrix, the tool runs, the admitted scanner findings and the complexity deltas;
- the context: the group-analysis report, the knowledge-base drift, and the review history for the category baseline.

`generate_consolidated_report` builds it once. Rendering is `render_markdown(report) -> str` and `render_console(report, console=None)`.

## Rejected alternatives

- **The report reads through the review session store (#771).** Rejected: a pure function of its input is tested without files, and the store can hand it the same input later. The refreshed plan of #1008 decided this.
- **The report takes the orchestrator.** Rejected: it keeps the coupling that the item removes, and a test would still build an orchestrator.
- **The report loads the history and the drift itself.** Rejected: the report would open files again. The orchestrator loads the history only when the session has findings, as `format_category_baseline_markdown` did, and the drift only when no group analysis ran.
- **The analyzer line moves into the module.** Rejected: it is computed from the analyzer states that the scan defines in `pipeline.py` (`ANALYZER_RAN` and the others), so the module would import the orchestrator's module, which imports the module. The executive summary already took the line as an argument.
- **One snapshot per section.** Rejected: one session that has each section holds the whole text at once. The sections that the session leaves out (the drift without a group analysis, the category baseline over a history) have unit tests.
