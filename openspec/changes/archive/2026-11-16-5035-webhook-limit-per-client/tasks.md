# Tasks

## 1. Rate limit for each client

- [x] 1.1 Write the failing gate check: the Middleware keys on `Cf-Connecting-Ip`, and only the tunnel reaches the Traefik `web` entrypoint from outside the cluster
  - Verification: `$ uv run python -c "from tests.gate.k8s import main; raise SystemExit(main())"`
- [x] 1.2 Key the Middleware on `sourceCriterion.requestHeaderName: Cf-Connecting-Ip`
  - Verification: `$ uv run python -c "from tests.gate.k8s import main; raise SystemExit(main())"`

## 2. Consumer events are a subset of the hook events

- [x] 2.1 Write the failing tests: row 7 is present for a hook that sends more events, wrong for a hook without `issues`, and each consumer event is an event that row 7 requires
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py`
- [x] 2.2 Name the consumers of the Service in `service_consumers`, and make row 7 check a subset
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py tests/server/test_server_service.py tests/telemetry/test_service_counter_series.py`

## 3. Documents

- [x] 3.1 Update setup steps 6 and 8 and the Webhook route section of `docs/CLUSTER.md`, and row 7 of `docs/roadmap/onboard.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Owner step O3 (tracker #5233, step 2): change Cloudflare Access on `hooks.<domain>/webhooks/github` to a Bypass for Everyone on that path only.
