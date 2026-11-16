## REMOVED Requirements

### Requirement: The written keep set matches the gateway config
**Reason**: The requirement only held a table of `k8s/README.md` equal to the gateway config, a value test of a document and a config file (#6060).
**Migration**: The prune reads the keep set from the gateway config of the tree at run time; the table of `k8s/README.md` explains it.
