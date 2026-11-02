# Tasks

## 1. Color a low-risk status green in the table

Reads: `src/devops_cli/security/reference_extractor.py`, `tests/security/test_reference_report_order.py`. Changes: `src/devops_cli/output/formatters/tables.py`, `tests/output/test_network_table_color.py` (new).

- [ ] 1.1 Write `tests/output/test_network_table_color.py`, with one parametrized test over six statuses: it builds a `NetworkReference` with each status, calls `format_network_references_table`, and asserts the status cell. "✓ Safe / Low Risk" and "LOW CONFIDENCE RISK" give `[green]...[/green]`. "⚠️ Flagged (known botnet)", "⚠️ Low Risk", "High Risk" and "MALICIOUS host" give `[red]...[/red]`. Verify that `uv run devops ci test tests/output/test_network_table_color.py` fails on the base
- [ ] 1.2 In `format_network_references_table` in `src/devops_cli/output/formatters/tables.py` (line 214), change the red condition `"RISK" in status_text` to `("RISK" in status_text and "LOW" not in status_text)`. Keep the other two terms of the condition (the warning sign and "MALICIOUS") and the yellow branch for "UNCHECKED" as they are, and verify that `uv run devops ci test tests/output/test_network_table_color.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
