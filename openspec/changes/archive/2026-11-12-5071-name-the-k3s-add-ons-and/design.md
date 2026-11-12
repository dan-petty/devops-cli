# Design

## Decisions

- Name the add-ons by the command that lists them, and give the list of k3s v1.37 as an example. A later k3s can add or remove an add-on, and the command stays correct.
- Name the annotation `objectset.rio.cattle.io/owner-gvk`, so that a reader can tell an object of an add-on from drift.
- Keep the fact that no alert reads the CoreDNS memory, and remove the reference to #4993. The change that adds an alert on the CoreDNS memory also changes that sentence (AGENTS.md rule 8).
- State the cleanup time as LiteLLM counts it: 24 hours after each start of the process. Give no measured count of runs, because the count changes with each rollout.

## Rejected alternatives

- Set `general_settings.maximum_spend_logs_cleanup_cron` so that the cleanup runs at a fixed time of day (`proxy_server.py` line 10356). It changes the behavior of the gateway, and #5071 is a document item. The measured delay is at most about 3 days, one run removes about 7 weeks of rows, and `GatewayDatabaseNearClaim` warns before the claim fills.
- Write each k3s add-on into git. k3s writes the packaged files again at each start, so git would hold a copy that k3s, not Argo CD, applies.
