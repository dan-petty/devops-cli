# Design

## Decisions
- One required order: the `Live since` comment on #4397, then the check in the MCP server pod, then the key, then a restart of the Service. The comment covers the Service and runner digests, and the check runs the real settings load of the MCP server image.
- The ConfigMap comment gives the two checks in short form and points to `docs/roadmap/stage.md` for the order.

## Rejected alternatives
- Compare the digests of CronJob `devops-cli-runner` and Deployment `mcp-server` with the digests of the release. It needs registry and cluster reads by hand, and it does not run the settings load.
- Keep the check of `deploy/roadmap-service` alone. It passes while the runner or the MCP server image is older, which is the defect of #4496.
- A test that reads the two texts and fails when they name only the Service. A check of prose in committed files matches words, not meaning, and docs/TESTING.md puts a check of committed files in a row of `devops ci`. The order step goes away when #4446 adds the key, so a permanent check costs more than it saves.
