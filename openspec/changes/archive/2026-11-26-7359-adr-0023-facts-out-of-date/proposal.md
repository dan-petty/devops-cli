# Proposal: #7359

## Why

Two facts in ADR 0023 (the project brain) are out of date after the work of 2026-11-26. The Status History of the record holds dated lines of the form "Fact out of date" for such cases, and it has none for these two. A reader takes the old facts as the state of the cluster and of the code.

## What Changes

Two dated lines in the Status History of ADR 0023:

- Section 8: `valkey-devops` has one ACL user for each role (#4704) and its default user is still on, so the rule of the section stays in force. `valkey-roadmap` has the users `brain`, `agent` and `metrics`, and its default user is off (#7294).
- Section 4: the sync step of the alternatives round copies each check again when its watermark is missing or has another schema, with no mark `brain-repair` and no run of repair (#4676).

No decision of the record changes.

## Capabilities

None. The change edits a decision record, and no behavior that a consumer observes changes.

## Impact

Readers of ADR 0023 and the agents that plan the open brain items (#4687, #6596, #6600) get the state of 2026-11-26.

## Feasibility

- `src/devops_cli/k8s/cluster_secrets.py` holds the ACL templates of the two stores: the template of `valkey-roadmap` starts with `user default off`.
- `_watermark_of` in `src/devops_cli/roadmap/brain_index.py` gives an empty watermark for a hash of another schema, and `sync_brain_index` in `src/devops_cli/roadmap/brain_sync.py` copies each check from an empty watermark.
- `grep -rn "brain-repair" src/devops_cli` finds no line.
- The live `valkey-devops` listed 5 ACL users on 2026-11-26, with the default user on (the progress review on #4624).

## Existing Tool Considered

None applies. The Status History of an ADR is edited by hand, as the line of 2026-11-20 was.
