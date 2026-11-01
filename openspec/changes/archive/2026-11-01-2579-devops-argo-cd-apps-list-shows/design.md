# Design

## Decisions

- **Show the repoURL of the first element of spec.sources for multi-source Applications.**: The first source is the primary source by Argo CD convention. This matches the Argo CD CLI behavior and keeps the column narrow and predictable.
- **Apply the fallback in both ArgoCDApp.from_api_item and ArgoResourceState.from_manifest.**: Both methods read spec.source.repoURL and both are used by the argo cd apps list command path. Fixing only one would leave the other path broken.

## Rejected alternatives

- **Join all repoURLs from spec.sources with a comma.**: Makes the column very wide and hard to read in a table. The issue asks for a single value with a stated rule.
- **Leave the Repo column empty for multi-source Applications.**: Preserves the current broken behavior. Does not fix the issue.
