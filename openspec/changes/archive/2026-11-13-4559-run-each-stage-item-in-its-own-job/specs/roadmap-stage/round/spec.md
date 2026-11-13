## REMOVED Requirements

### Requirement: The Service runs the stage job on the model lane
**Reason**: The stage job of each item runs in a stage Job of its own, so a rollout of the Service stops no plan (#4559).
**Migration**: The row `stage` of the status lane submits the stage Jobs. The requirement "The status lane submits one stage Job for each Ready item" of `roadmap-stage/job` holds the rule, and its interval, its first run and its `stage_due` stamp stay as they were.

### Requirement: The row fails only when no item was handled
**Reason**: The row tries no item: a stage Job plans it and records its failure on the item, so the row fails only for an error that belongs to no item (#4559).
**Migration**: A failed item waits for the wait of its class, and its counted ends return it for a split. The requirement "The stage row recovers a Job that ended with no check-in" of `roadmap-stage/job` holds the rule.
