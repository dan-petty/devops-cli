# Design

## Decisions

- **Exclude "LOW" from the "RISK" test in `tables.py`, with the same words as `_network_security_severity_rank`.**: The function sorts the rows, so the order and the color of a row then agree: a status that sorts as safe is green, and a status that sorts as flagged is red. The red rule becomes `"⚠️" in s or ("RISK" in s and "LOW" not in s) or "MALICIOUS" in s`.
- **Keep two rules and do not share a helper.**: The rank is a sort key with six tiers. It also puts "CRITICAL", "FLAGGED" and "HIGH" in the flagged tiers. If the table took its red from the rank, it would turn "CRITICAL", "FLAGGED" and "HIGH" red (probe of `main`: all three give `[green]` today and ranks 0, 1 and 1). That changes colors that #2646 does not name. The product writes a red status only with the warning sign, so this would not show today, but it is a second behavior change in a fix. The report row has a third rule (warning sign only, and cyan for a local reference). A shared helper needs a decision on all three, which is a separate item.
- **A status with both "LOW" and "RISK" is green.**: "LOW CONFIDENCE RISK" turns green, and the rank gives it rank 4, a safe rank, for the same reason (probe of `main`: `LOW CONFIDENCE RISK` gives `[red]` today and rank 4). A status with the warning sign stays red, also with "LOW": "⚠️ Low Risk" gives `[red]` and rank 1. The product writes no status with both words and no warning sign, other than "✓ Safe / Low Risk". The requirement of the spec holds this rule, and the scenarios name the two cases that the product writes.

## Rejected alternatives

- **Color red only a status with the warning sign, as `_network_reference_row` in `report.py` does.**: The table would turn "MALICIOUS host" and "High Risk" green (probe of `main`: both give `[red]` today). `git grep -n MALICIOUS src` finds no producer of that word, so the rule is defensive today, but the issue asks for a green "Low Risk" only. The refine step of the issue chose to keep the other red words.
- **Use a structured severity field instead of string matching.**: `NetworkReference.security_status` in `src/devops_cli/models/vulnerability.py` is a plain string, and the pipeline, the report, the JSON output and the sort all read it. A severity field changes all of them, which is more than one pull request for a color.
- **Take the color from `_network_security_severity_rank`.**: See the decision on two rules. It changes the color of statuses that the issue does not name.
