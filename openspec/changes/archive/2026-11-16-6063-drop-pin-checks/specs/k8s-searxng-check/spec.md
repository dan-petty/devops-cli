## REMOVED Requirements

### Requirement: Pinned image
**Reason**: The owner decided on 2026-11-16 (#6060) that a SearXNG image updates like any other image, so no check compares the Deployment with an image of the command.
**Migration**: None. `devops k8s searxng-check` tests the running service, whatever image it runs.

### Requirement: Reply fixture from the pinned image
**Reason**: The test compared the fixture with `SEARXNG_IMAGE`, which is removed (#6063). The provider tests still read `search_reply.json`.
**Migration**: None.
