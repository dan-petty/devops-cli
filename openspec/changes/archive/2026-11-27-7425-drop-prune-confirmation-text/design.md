# Design

## Decisions

- **Keep step 13 as a record.** The switch is done, and the steps tell how the prune was first turned on. One paragraph states the current behavior and names the change that made it.
- **Remove the generator annotation.** `Prune=true` let a hashed ConfigMap prune with no confirmation. With no confirmation, the default prune does the same.
