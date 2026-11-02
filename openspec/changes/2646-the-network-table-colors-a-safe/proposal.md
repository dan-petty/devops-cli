# Proposal

## Why

#2646 reports that the table of network references shows a safe reference in red. The status "✓ Safe / Low Risk" holds the text "RISK", and the color rule of `format_network_references_table` in `src/devops_cli/output/formatters/tables.py` turns every status with that text red. Red is the color of a flagged reference, so a reader sees a safe reference as a danger.

## What Changes

- The red rule of the table stops at a status that holds "LOW": "RISK" gives red only when "LOW" is not in the status. The warning sign and "MALICIOUS" still give red, and "Unchecked" stays yellow.
- A new test in `tests/output/test_network_table_color.py` checks the color of six statuses: "✓ Safe / Low Risk" and "LOW CONFIDENCE RISK" green, and "⚠️ Flagged (known botnet)", "⚠️ Low Risk", "High Risk" and "MALICIOUS host" red.
- The spec `threat-intel-lookup-outcome` gets one new requirement for the red and green colors of the table. Its requirement "An unchecked reference ranks above a safe one" already holds the yellow color, so this change does not repeat it.
- The code and the test are observable behavior of the table, so the change has a spec delta.
- The pull request that delivers the code closes #2646 and cites its `devops ci fail-to-pass --base origin/main` run. This pull request only plans.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `threat-intel-lookup-outcome`: The table colors a low-risk status green and a flagged status red

## Impact

- Code: `src/devops_cli/output/formatters/tables.py`
- Tests: `tests/output/test_network_table_color.py`

## Feasibility

Run on `main` at commit `24ef67ac`, with devops-cli 0.45.0 and Python 3.14. The probe makes no network request.

Check 1: the command of the issue shows the defect. It prints `[red]✓ Safe / Low Risk[/red]`.

```text
uv run python -c "from devops_cli.models.vulnerability import NetworkReference; from devops_cli.output.formatters.tables import format_network_references_table as f; print(f([NetworkReference(target='https://safe-corp.com', security_status='✓ Safe / Low Risk')]).rows[0][3])"
```

Check 2: the same call for each status that the product writes and for the red words of the table. The product writes "✓ Safe / Low Risk", "✓ Safe (Local)", "✓ Safe (Ports: 80)", "✓ Safe (Documented Example)", "Unchecked" and "⚠️ Flagged (...)" (`src/devops_cli/ai/review/pipeline.py` lines 836 to 848, `src/devops_cli/security/reference_extractor.py` lines 543 to 597). Only the first one has the wrong color:

```text
'✓ Safe / Low Risk'    [red]    (should be green)
'✓ Safe (Local)'       [green]
'✓ Safe (Ports: 80)'   [green]
'Unchecked'            [yellow]
'⚠️ Flagged (botnet)'  [red]
'High Risk'            [red]
'MALICIOUS host'       [red]
```

Check 3: the line `if "⚠️" in status_text or "RISK" in status_text or "MALICIOUS" in status_text:` is at `tables.py` line 214. The same text with "LOW" excluded, `("RISK" in s and "LOW" not in s)`, is at `reference_extractor.py` line 609, in `_network_security_severity_rank`. That function ranks a status to sort rows. It gives "✓ Safe / Low Risk" rank 4, a safe rank, and "High Risk" rank 1, a flagged rank. The table therefore sorts the row as safe and colors it red. The review report does not use this rule: `_network_reference_row` in `src/devops_cli/review/report.py` (line 844) colors only a status with the warning sign red.

Check 4: no test sets the color of a red or green row. `tests/security/test_reference_report_order.py` line 167 checks yellow and green for "Unchecked" and "✓ Safe (Ports: 80)" only, so the new test is needed.

Check 5: a trial of the plan in a scratch copy, not committed. With the test of task 1.1 and the old condition, `uv run devops ci test tests/output/test_network_table_color.py` gave `2 failed, 4 passed` (the two green cases failed). With the new condition it gave `6 passed`.

## Existing Tool Considered

No library colors a free-text status. Rich only renders the markup tag that the code chooses. The change builds a one-line condition in the project's own code. Written cost, estimated from the agent runs that planned it: about 15,000 tokens to write the test and the condition, about 5,000 tokens to keep it (a new status word needs one new test row), and about 10,000 tokens to fix it if the rule is wrong. Elapsed time: about 20 minutes for one pull request, with a CI run of under 5 minutes. The change deletes no internal code.
