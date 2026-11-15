# Proposal: #4446

## Why

`ai.decision_model` exists since #4397, and `AIConfig` refuses a key that it does not know. The
Service, runner and MCP server images now know the key, but the example ConfigMap named no value,
so a point could not record a shadow answer unless a person edited the live ConfigMap, and
`devops k8s deploy-stack` then removed that edit. Closes #4446.

## What Changes

- `k8s/devops/configmap.example.yaml` sets `decision_model: typesafe/jev-1.14` under `ai`, and its
  comment records the live check of the three images.
- `tests/k8s/test_k8s_configmap.py` asserts the rendered settings name the decision model.

## Capabilities

`decision-workflows`: one requirement for the template value and its live proof.

## Impact

The devops ConfigMap only. With the setting, a point in the mode `shadow` records the answer of the
model, and a point in `off` or `on` keeps its mode from `roadmap.decisions` (ADR 0020). No image,
command or gateway change.

## Feasibility

Premise checked on 2026-11-15 against the live cluster and `origin/main` (ca62d6a9f):
`devops config get ai.decision_model` prints an empty value and exits 0 in
`deploy/roadmap-service`, in the running implement Job pod and in `deploy/mcp-server`, and the
setting is in `AIConfig`.

## Existing Tool Considered

The ConfigMap template is the file that `devops k8s deploy-stack` already renders. No tool is
needed for one setting and one comment.
