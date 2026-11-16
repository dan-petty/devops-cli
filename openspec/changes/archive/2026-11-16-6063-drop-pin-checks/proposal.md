# Proposal: #6063

## Why
Each Renovate update of SearXNG and each chart update failed until a person edited the tests: the `k8s` gate row compared the SearXNG image with `SEARXNG_IMAGE`, two SearXNG tests compared fixtures with the pinned image, and the claim and token tables keyed each entry on the chart version (PRs #6029, #6046, #6055). The owner decided on 2026-11-16 (#6060, comment "Owner decisions, 2026-11-16"): remove the SearXNG gate and its pin tests, so a SearXNG image updates like any other, and drop the chart versions from the tables, so a chart update no longer touches them. Closes #6063.

## What Changes
- The `k8s` gate row no longer compares the image of Deployment `searxng` with `SEARXNG_IMAGE`.
- `SEARXNG_IMAGE` is removed. `devops k8s searxng-check` tests the running service and its report names no image.
- The engine-names tests of `tests/invariants/test_k8s_searxng.py`, the saved-reply test and the image test of `tests/k8s/test_searxng_check.py` are removed, with `default_engine_names.txt` and `search_reply_image.txt`. `search_reply.json` stays, because the provider tests read it.
- `CHART_CLAIMS` and `_CHART_TOKENS` key each entry on the chart name. Their tests still fail when a pinned chart has no entry; the claim and token rules stay.
- The SearXNG note and description of `.github/renovate.json`, `docs/CLUSTER.md` and `k8s/README.md` describe the result. The test of the note, which read a `renovate.json` value, is removed.

## Capabilities
- `k8s-searxng-check`: the requirements "Pinned image" and "Reply fixture from the pinned image" are removed.
- `searxng-service`: the requirements on the kept engines and on the note of a bump change.

## Impact
- The closed Renovate updates for SearXNG and the charts pass the gate and these tests when Renovate opens them again.
- `docs/SDLC.md` names `_CHART_TOKENS` in a sentence that PR #6057 rewrites; this change leaves that line to #6057, so the two pull requests do not conflict.

## Feasibility
- PR #6055 (grafana 14.4.2) failed only at the two table tests and the deploy-stack version tests; the table tests pass with name keys.
- `SEARXNG_IMAGE` had one runtime use: the image named in the success message of `devops k8s searxng-check`.
- `rg search_reply.json tests` shows `tests/ai/test_web_search_searxng.py` reads the reply, so the reply stays.

## Existing Tool Considered
No tool is needed: the change removes checks. The open validators that CI runs keep checking the manifest form.
