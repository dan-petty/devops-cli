# Design

## Decisions

- **A dated line in the Status History, not a rewrite of the section.** The record keeps the text that the owner approved, and the line of 2026-11-20 set the form "Fact out of date" for a fact that changed.
- **The rule of section 8 stays.** The condition of the section has two parts: one ACL user for each role, and the default user off. Only the first part is true for `valkey-devops`, so the line says that the rule stays in force.

## Rejected alternatives

- **Rewrite sections 4 and 8.** The due marks and the repair run are open work (#4687, #6596), so a rewrite now would state a design that is not decided.
- **A new ADR.** No decision changes.
