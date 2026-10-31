# Design

## Decisions

- **A fixed rule names the skip classes, not the model**: Over 14 days the model searched about 4 times and returned not-applicable every time. A fixed rule is deterministic and testable.
- **The constant list lives in the alternatives check module**: The issue body says the classes live in one constant list with a test. A constant in the same module as the check keeps the rule and its enforcement together.
- **Reject a no-search reply and give the model one turn to search**: The issue body records this mechanism. It gives the model a chance to search while still enforcing the rule.
- **A second no-search reply ends as a failed check**: The issue body says a second answer without a search ends as a failed check for that item.
- **The verdict for skip-class items is not-applicable with the class name as the reason**: The issue body records this. It is consistent with the existing not-applicable verdict in CONTEXT.md and gives a person a clear reason.

## Rejected alternatives

- **Let the model decide whether to search**: Over 14 days the model searched about 4 times and returned not-applicable every time (issue body, devops_cli_roadmap_alternatives_total). It is not reliable for this gate.
- **Store the skip classes in a separate configuration file**: The list is a fixed rule, not a user setting. A config file adds indirection without benefit.
- **Hardcode the skip classes in the model prompt**: The issue body says a fixed rule, not the model, names the classes. A prompt is not a fixed rule.
- **Hard-fail immediately on the first no-search reply**: The issue body says the model gets one turn to search. Hard-failing gives the model no chance to correct.
- **Warn and continue with the no-search verdict**: The issue body says the reply is rejected. Warning does not enforce the rule.
