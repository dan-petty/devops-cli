# Design

## Decisions

- **Exclude 'LOW' from the RISK check in the table formatter.**: Matches the existing pattern in reference_extractor.py line 609. Keeps 'High Risk' red and makes 'Low Risk' green.
- **Keep 'MALICIOUS' as a separate red trigger.**: A status can hold 'MALICIOUS' without holding 'RISK'. Removing it would lose the red color for such statuses.

## Rejected alternatives

- **Check only for '⚠️' as the red trigger.**: This would leave 'MALICIOUS' and 'High Risk' without the warning sign uncolored red, losing information.
- **Use a structured severity field instead of string matching.**: The NetworkReference model does not expose a severity enum. The string-based approach is the existing convention in this codebase.
