## REMOVED Requirements

### Requirement: No process of a step lives when the job runs git or gh
**Reason**: The runner Job runs the agent phase in its own container, which holds no App key and no token, and the processes of the agent end with that container (#3700). No git or gh child with the token runs next to them, so the job adopts no orphans and ends no process of a step (#6691).
**Migration**: None.
