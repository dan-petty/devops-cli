## REMOVED Requirements

### Requirement: Pinned image
**Reason**: The check of the `k8s` row held the image of Deployment `crawl4ai` equal to `CRAWL4AI_IMAGE`, so each Renovate update of the digest failed CI although no code changed. The owner asked to remove each test and gate check that blocks a Renovate update (#6060).
**Migration**: A person runs `devops k8s crawl4ai-check` after each bump of the digest, as `docs/CLUSTER.md` says. The command names no image.
