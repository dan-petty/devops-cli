# Tasks

## 1. Fix low-risk color in network table

Reads: none. Changes: `src/devops_cli/output/formatters/tables.py`, `tests/output/test_network_table_color.py` (new).

- [ ] 1.1 Write a test that creates a NetworkReference with security_status '✓ Safe / Low Risk' and asserts the status cell is wrapped in [green]...[/green]. Also assert '⚠️ High Risk Detected' renders [red]...[/red] and 'Unchecked' renders [yellow]...[/yellow], and verify that `uv run pytest tests/output/test_network_table_color.py -v` fails on the base
- [ ] 1.2 Change the condition on line 214 of `src/devops_cli/output/formatters/tables.py` from `if "⚠️" in status_text or "RISK" in status_text or "MALICIOUS" in status_text:` to `if "⚠️" in status_text or ("RISK" in status_text and "LOW" not in status_text) or "MALICIOUS" in status_text:`. This matches the pattern in `src/devops_cli/security/reference_extractor.py` line 609, and verify that `uv run pytest tests/output/test_network_table_color.py -v` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
