# Design

## Decisions
- **Key on `Cf-Connecting-Ip`.** Each request gets to Traefik through the tunnel, so its remote address is a cloudflared pod, and its host is `hooks.<domain>` for each sender. Only `Cf-Connecting-Ip` tells one client from another. The Cloudflare edge sets it to the address of the client and overwrites a value that the client sends. The header holds one address, so no depth is necessary.
- **Spoofing.** A client outside the cluster cannot set the key: the tunnel is its only path to Traefik, and the edge writes the header. A pod of the cluster can reach the `ClusterIP` Service of Traefik and set any value, so it can get a new bucket for each request. The HMAC check still refuses its deliveries, and such a pod is inside the cluster boundary. A request with no header (only a pod can send one) goes into one shared bucket, because Traefik reads an empty value.
- **Rate and burst stay.** 60 a minute with a burst of 60 for each client. GitHub sends from more than one address, so its deliveries get more space than before.
- **Consumer events are a subset of the hook events.** Row 7 requires each event of `CONST_ROADMAP_WEBHOOK_EVENTS` of the hook, and lets the hook send more. The live hook sends `issues`, `milestone`, `pull_request` and `release`, and the Service acknowledges an event that no consumer takes. `service_consumers` names the consumers of the Service, so the test reads the same set that the router uses.

## Rejected alternatives
- **`ipStrategy.depth: 1` on `X-Forwarded-For`.** A client can send its own `X-Forwarded-For`, and Cloudflare appends to it. The right depth depends on each proxy of the chain. `Cf-Connecting-Ip` holds one value that the edge writes.
- **`ipStrategy` with `ipv6Subnet`.** Traefik applies `ipv6Subnet` only to the depth and remote address strategies, not to a header. A sender with many IPv6 addresses gets more buckets of its own, but it cannot use the bucket of GitHub.
- **A second, global bucket.** One shared bucket behind the per-client bucket would let a flood fill it, and GitHub would lose deliveries again.
- **A Cloudflare rate-limit rule.** No OpenTofu under `tf/` manages Cloudflare, so the rule would be a dashboard change that is not in git.
- **Equal events in row 7.** The live hook sends more events than the Service takes, and the next consumers (#4413, #4416, #6013) need them. Equality reports such a hook as wrong.
