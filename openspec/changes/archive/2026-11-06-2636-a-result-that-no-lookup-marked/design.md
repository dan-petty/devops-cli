# Design

## Decisions

- **Make security_status and status required (no default) rather than defaulting to an unchecked sentinel value**: A required field forces the producer to set the status. A validation error appears if the field is missing. A sentinel default would require every consumer to check for it, and a consumer that does not check would treat the sentinel as a valid status.
- **Remove NetworkIntelResult and PackageIntelResult rather than making their fields required**: No code in src/ uses these two models. Only tests/models/test_resource_schemas.py builds them. Removing them eliminates dead code and its maintenance cost. Making their fields required would keep dead code alive.

## Rejected alternatives

- **Default security_status and status to an unchecked sentinel value**: A consumer that does not check for the sentinel would treat it as a valid status. The #2504 design doc rejected the same pattern for LookupOutcome: 'a forgetful client would show Unchecked with no error'.
- **Keep NetworkIntelResult and PackageIntelResult with required fields**: No code in src/ uses these models. The issue confirms only tests/models/test_resource_schemas.py builds them. Keeping them adds a maintenance cost for models that no producer uses.
