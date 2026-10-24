# Spec Delta

## Purpose

The routes of `devops ai gateway`: the model and the Ollama Service that each virtual model of the gateway uses, and the route that a failover of a virtual model records.

## ADDED Requirements

### Requirement: Every gateway route names a model that its tier serves
Each default route of `devops ai gateway`, and the route that a failover of each virtual model records, SHALL name a model that a deployment of the gateway config sends to a serving tier that the route's Ollama Service selects.

#### Scenario: The default routes
- **WHEN** `devops ai gateway routes` lists a new route table
- **THEN** each route names a model that the gateway config sends to a serving tier of the route's Service

#### Scenario: The route that a failover records
- **WHEN** each virtual model fails over on a new route table
- **THEN** the route that the failover records names a model that the gateway config sends to a serving tier of the route's Service

### Requirement: A failover to direct Ollama keeps the model of the default route
When a virtual model fails over to `direct-ollama`, the route that the failover records SHALL name the target model of the virtual model's default route, on the default Ollama Service, with the backend type `failover:ollama`.

#### Scenario: devops-chat fails over
- **WHEN** `devops-chat` fails over on a new route table
- **THEN** its route names `qwen3.8:27b` on the default Ollama Service, with the backend type `failover:ollama`
