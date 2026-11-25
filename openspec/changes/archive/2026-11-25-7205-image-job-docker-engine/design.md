# Design

## Decisions
- The default builder of the Docker Engine builds the images of a pull request.

## Rejected alternatives
- `cleanup: false` on `setup-buildx-action`: it saves the removal only, and keeps the tar transfers.
- One job for each image: it adds hosted jobs, which #4649 removed.
- The same change in the release: its jobs are inside the limit, and it pushes by digest with attestations.
