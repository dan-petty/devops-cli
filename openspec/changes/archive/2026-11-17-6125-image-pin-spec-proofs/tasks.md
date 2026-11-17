# Tasks

## 1. The specs of the images, the release pins and the devcontainer (other)

- [x] 1.1 Write the deltas of the 7 capabilities: each scenario that read a file names a validator command, a live check, an install, a build or a dry run; each requirement that only restates a file goes; each requirement with a scenario that can only describe a read goes out and comes back under a new name.
  - Verification: `$ uv run devops openspec check`
- [x] 1.2 Archive the change into the living specs, and count the census of the area and of all specs before and after.
  - Verification: `$ uv run devops openspec check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
