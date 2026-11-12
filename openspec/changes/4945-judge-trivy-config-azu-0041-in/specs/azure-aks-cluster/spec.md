## Purpose
The Azure OpenTofu module provisions an AKS cluster whose network profile enforces Kubernetes network policies with the policy engine native to its CNI plugin.

## ADDED Requirements

### Requirement: The AKS network profile sets a network policy
The Azure OpenTofu module SHALL set a network policy engine in the network profile of the AKS cluster, which is the condition that the Trivy-config check AZU-0041 requires.

#### Scenario: The network profile holds a policy engine
- **WHEN** the Azure module is parsed
- **THEN** the network profile of the AKS cluster sets a network policy engine beside its network plugin.

### Requirement: Azure CNI selects the Azure network policy engine
The AKS cluster SHALL use the Azure network policy engine when its network plugin is Azure CNI.

#### Scenario: The Azure plugin gets the Azure policy
- **WHEN** the network profile sets the Azure network plugin
- **THEN** the network profile sets the Azure network policy engine.
