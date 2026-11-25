## Problem Description

The comment of `devops roadmap alternatives` shows at most five sources. When the reply cites more, it shows the first five and the line "N more sources are left out". `CONST_ROADMAP_ALTERNATIVES_MAX_COMMENT_SOURCES` sets this bound.

On 2026-11-17 the owner said that the jobs must have no hard caps that make a job fail or lose context. Refine, stage and implement read this comment as context, so the bound removes sources that they could read. Since #6174 (#6168), the sources are in the closed `<details>` block, so a long list of sources does not make the open comment longer.

## Reproduction Steps

1. Give the check a reply that cites eight sources that the tools returned.
2. Read the comment: it lists five sources and the line "3 more sources are left out".

## Expected vs Actual Behavior

Expected: the closed block lists every source of the reply, and the comment has no "left out" line.

Actual: the comment lists five sources and leaves out the others.

## Environment Diagnostics

devops-cli at 3f422adcb (after #6174).

## Logs, Traces, or Terminal Output

None.


Source: https://github.com/dan-petty/devops-cli/pull/6174

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
