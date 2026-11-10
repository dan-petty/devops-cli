# Design

## Decisions

- **A Secret of its own for the server.** The pod reads `devops/mcp-server` with `secretKeyRef`, as Deployment `crawl4ai` does. The pod already loads `devops-cli` with `envFrom`, so the key could live there. A key in the Secret of the server names its use, and the secret table restarts only the workload that needs the restart.
- **One keyring entry, three keys.** The server accepts one token. Each client key reads the entry of `mcp.token`, and so a rotation changes the server and the clients in one push. Keyring names for `mcp.stage_token` and `mcp.implement_token` stay unused in the cluster.
- **Optional client keys.** Both client switches are off, so a push without the token must not fail for them. The server key is required, because the pod cannot start without it.
- **A key-level guard.** The test that a table row exists for each Secret did not see a missing key. The new test checks each `secretKeyRef` to a Secret of the table against the keys of its row.
- **The URL in the example.** `roadmap.mcp.url` is in the ConfigMap example with the switches off. The image knows the key already, so the apply order between the ConfigMap and the image does not matter.

## Rejected alternatives

- **A separate token for each role.** Rejected: `BearerTokenVerifier` holds one digest, and a second token is new server code that no consumer needs yet.
- **A token in the ConfigMap or the manifest.** Rejected: SECURITY.md keeps secrets out of the repository.
- **A fix of the NetworkPolicy labels in this change.** Rejected: the Jobs of the Service carry the label `devops-cli-job`, not `devops-cli-runner`. The fix needs a decision about the scope of the label, so it has its own issue (#4355).
