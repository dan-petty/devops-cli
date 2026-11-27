## REMOVED Requirements

### Requirement: The example ConfigMap holds the runner memory limit
**Reason**: The setting `roadmap.implement.max_memory_limit` is removed. The memory limit of a runner Job equals the memory request of its row (#7422).
**Migration**: The section `roadmap.implement` ignores the key, so the live ConfigMap loads while it holds the key. Remove the key from the source of the ConfigMap.
