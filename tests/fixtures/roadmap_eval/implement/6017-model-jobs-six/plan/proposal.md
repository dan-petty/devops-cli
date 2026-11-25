# Proposal: #6017

## Why
PR #6009 (#5027) added `roadmap.model_jobs`: the most implement, stage and fix-checks Jobs that run at once for all repositories of the Service together, with the fix-checks Jobs first. Its code default is 2. Before #6009, each repository had its own lock of one implement Job. The owner chose 6 on 2026-11-16 (#6017).

## What Changes
- `k8s/devops/configmap.example.yaml` sets `roadmap.model_jobs: 6` under `roadmap:`, with a comment that names the owner choice.
- The code default stays 2.

The ConfigMap template is a manifest, so the change has a spec delta.

## Capabilities
- `roadmap-fix-checks`: one added requirement for the value of the cluster template.

## Impact
The ConfigMap template only. A deploy-stack after the release that holds #6009 applies it; an image from before #5027 ignores the key. The change fits one pull request.

## Feasibility
`RoadmapConfig.model_jobs` reads the key (`src/devops_cli/config/settings.py`), and a test reads the rendered template with the settings model.

## Existing Tool Considered
None applies: the change sets one value of an existing setting. It deletes no code.
