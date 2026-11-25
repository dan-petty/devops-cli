# Design

## Decisions
- Background steps keep the step list flat, so the tests that read the steps of `ci.yml` still see each one.
- The scans start where they ran before, after the smoke test of their image, so a broken image still fails before its scan.
- One Trivy cache directory for each category: the file cache of Trivy serves one process.

## Rejected alternatives
- One job for each image: each job builds its image again, and #4649 removed such jobs.
- `--cache-backend memory` with one shared directory: the pass that prints the findings reads the cache of the scan, and would read the image again.
- No scan of the runner image in pull requests: it removes coverage, and only the owner can decide that.
- A stored Java database: the restore of about 1 GB takes about as long as the download.
