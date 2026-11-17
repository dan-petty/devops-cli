# Tasks

## 1. The specs of Kubernetes, the cluster and the stacks (other)

- [x] 1.1 Write the deltas of the 19 capabilities: each scenario that read a manifest names a validator command, a live check or a dry run; each requirement that only restates a file goes; each requirement with a scenario name that says "A test reads" goes out and comes back under a new name.
  - Verification: `$ uv run devops openspec check`
- [x] 1.2 Archive the change into the living specs, and count the census of the area and of all specs before and after.
  - Verification: `$ uv run devops openspec check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
