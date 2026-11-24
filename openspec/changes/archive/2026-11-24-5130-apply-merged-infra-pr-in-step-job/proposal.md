# Proposal: #5130

## Why
After a pull request of an infra repo merges, hosts wait for a person or workstation agent to apply the merge commit. Closes #5130.

## What Changes
This change adds an `infra-apply` step job and webhook handler that plans and applies merged pull requests.
It enforces agent access level `safe` or `full`.
It plans the merge commit and applies the plan only when the plan status is `ok`.
It stops before a disruptive host that is the pod node or control-plane node, and reports that a workstation run is required.
It posts exactly one comment with the result and audit record on the merged pull request.
It opens or updates an issue in the infra repo on failure.

## Capabilities
- `infra-apply`: Run infra apply step job on merged pull requests of infra repositories.

## Impact
- Automated execution of infra applies in cluster Job pods upon pull request merge.
- Safe execution preventing disruptive runs against own pod node or control-plane nodes.

## Feasibility
- `devops infra plan` and `devops infra apply` already exist in the codebase.
- The webhook router and cluster runner mechanisms already support step jobs.

## Existing Tool Considered
- Atlantis and generic GitOps tools do not integrate with `devops infra apply`, cluster node guards, or roadmap step jobs. Building this internal step job fits the existing roadmap runner architecture.
