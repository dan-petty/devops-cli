# Proposal: #3772

## Why

The Service runs a repository's scoped update at once when a webhook arrives. Without the webhook, the repository waits for a poll. Onboarding has no row for the webhook, so a repository can be onboarded with no webhook, or with a wrong URL, content type or event set, and nobody sees it. `docs/CLUSTER.md` step 8 tells a person to add it by hand. Closes #3772.

## What Changes

- `devops roadmap onboard` gains a read-only row 7, `webhook`: it reads `GET repos/<owner>/<name>/hooks` and reports `present`, `missing`, `wrong` (naming the field) or `not readable as <login>`.
- The row compares each hook with the new setting `service.webhook_url` (default `https://hooks.example.com/webhooks/github`), the `json` content type and the events of `CONST_ROADMAP_WEBHOOK_EVENTS`.
- A missing or wrong row prints the step for a person: the URL, the content type, the events, and `devops config set service.webhook_secrets`. It prints no secret and creates no hook.
- `docs/roadmap/onboard.md` describes the row, and a test holds the step and the events of `docs/CLUSTER.md` step 8 together.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-onboard`: The webhook row.

## Impact

- Code: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/settings.py`
- Documents: `docs/roadmap/onboard.md`, `docs/CLUSTER.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- Tests: `tests/roadmap/test_roadmap_onboard.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `3f355e278`.

- The command checks six rows: `src/devops_cli/roadmap/onboard.py:230:def check_onboarding`.
- The REST client has no hooks read: `src/devops_cli/github/client.py`, and `session.paginate` covers the page.
- The event set exists: `src/devops_cli/config/constants.py:3759:CONST_ROADMAP_WEBHOOK_EVENTS`.
- The person's step is `docs/CLUSTER.md:39`, step 8.
- The new tests pass on the branch: `uv run devops ci test tests/roadmap/test_roadmap_onboard.py`.

## Existing Tool Considered

The GitHub REST API lists the hooks, and the project's session paces, charges and retries the request. No open tool models a repository's webhook state for onboarding, and the row writes nothing. The cost is about 120 lines of code and 200 lines of tests.
