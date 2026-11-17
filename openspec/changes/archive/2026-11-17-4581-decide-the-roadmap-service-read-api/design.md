# Design

## Decisions

- **Record the choice in an architecture decision record, MADR 4 form.**: The choice is difficult to reverse: it fixes an interface, the exposure and the auth of the Service.
- **Place the API in the webhook router.**: It is the one long-running process that the move keeps, it already serves HTTP, and it holds the Service settings.
- **Read `valkey-roadmap` only.**: ADR 0021 moves the state there, and a read that sends no GitHub request and no model request keeps the rate-limit and model budgets.
- **Keep the API in the cluster, with no Ingress.**: ADR 0003 keeps every other route of the Service private.
- **One named read-only token for each reader, compared in constant time.**: Grafana gives anonymous viewers what its token reads, from the home address with no login, so the token is read-only and the fact is recorded.
- **No write route in v1, and the open tool of each write named.**: A pause that lives only in Valkey would break the rule that Valkey never holds the only copy of a decision.

## Rejected alternatives

- **A separate read Deployment**: it adds a second process, image and settings source.
- **An Ingress and a Cloudflare Access application**: it widens the exposure that ADR 0003 keeps private.
- **A read of the process memory**: ADR 0021 moves the state into Valkey.
- **Write routes in v1**: they break the rule that Valkey never holds the only copy of a decision.
