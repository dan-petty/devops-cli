## MODIFIED Requirements

### Requirement: The Popeye tool runs the Popeye adapter over the namespace
The agent tool `scan_popeye` SHALL run the Popeye adapter of `devops_cli.security` over the namespace that the agent names, or over the namespace of the current context when the agent names none. Popeye SHALL start in a new empty directory, in the sandbox with the network profile `kube-api`. The tool SHALL keep no command line of its own, and SHALL reply as the other agent scan tools reply.

#### Scenario: Popeye finds issues in a namespace
- **WHEN** the agent calls `scan_popeye("argocd")`, and Popeye reports six issues at warn and error level
- **THEN** Popeye starts in an empty directory with `popeye -o json -l warn -n argocd`, and the reply is `Popeye scan status: ok`, then `Findings (6):`, then one line for each finding
