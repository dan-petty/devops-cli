# mcp-server-network-policies Specification

## Purpose
Which pods may call the MCP server in namespace `devops`, and on which port.

## Requirements

### Requirement: The policies admit the Job pods and the Service
`mcp-server-ingress` SHALL admit TCP 8001 to the pods of the MCP server from the pods with the label `app.kubernetes.io/name` of `roadmap-service` or of the pod label that `build_job` sets on a Job pod. `mcp-server-clients` SHALL select the same two label values and SHALL admit egress of TCP 8001 to the pods of the MCP server only.

#### Scenario: A test reads the policies and builds a Job
- **WHEN** a test builds a Job with `build_job` from CronJob `devops-cli-runner` and reads the two policies
- **THEN** the label of the Job pod is in both policies, and the two policies admit the same two label values

### Requirement: Nothing else is open
Each of the two policies SHALL hold one rule, with TCP 8001 as its only port, and SHALL name no namespace selector and no address block.

#### Scenario: A test reads the policies
- **WHEN** a test reads the two policies
- **THEN** each holds one rule, with port 8001 and a pod selector only
