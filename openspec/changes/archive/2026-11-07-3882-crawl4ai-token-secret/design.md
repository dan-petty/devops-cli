# Design

## Overview

One keyring value, `crawl4ai_api_token`, backs two entries of the secret table: `CRAWL4AI_API_TOKEN` in Secret `devops/crawl4ai` and `DEVOPS_CLI_CRAWL4AI_API_TOKEN` in Secret `devops/devops-cli`. The push reads the keyring, adopts the live value, or generates one, as it does for the other rows.

## Decisions

- The generator is on the row `devops/crawl4ai` only. The row comes before `devops/devops-cli` in the table, and the plan counts a generated value as the keyring's own for the later entries. A push of `devops/devops-cli` alone, with an empty keyring, adopts the value of `devops/crawl4ai` from the cluster, else skips the optional entry with a warning.
- The entry in `devops/devops-cli` is not required, so the roadmap Service starts without a Crawl4AI client configured.
- The credential has no settings field and no getter. The client that reads it comes with its own issue, so no unused code lands here.
- The row restarts no workload until a manifest holds Deployment `crawl4ai`, because a gate test refuses a restart target that no manifest holds. #3884 adds the restart with the manifest.

## Rejected Alternatives

- **A generator on both entries**: it works in any order, but it lets a push of `devops/devops-cli` alone make a token that the service Secret does not hold yet. The adopt-from entry gives one owner of the value.
- **`deployment/crawl4ai` in `restarts` now**: `tests/invariants/test_k8s_manifests.py::test_every_restart_target_is_a_manifest_workload_or_helm_release` fails. An exception in that test would hide a real typo in a later row.
