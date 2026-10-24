# Spec Delta

## Purpose

The Valkey servers of the llm namespace in the cluster manifests: the cache Valkey that holds Open WebUI's state and the run index that workstations share. It says how much memory each one keeps as data and what each one does when its data reaches that bound.

## ADDED Requirements

### Requirement: Each llm Valkey refuses writes at a memory bound below its container limit
The valkey container of each Valkey Deployment in `k8s/llm/` SHALL start valkey-server with `--maxmemory` at most three quarters of the container's memory limit, and with `--maxmemory-policy noeviction`, so that Valkey refuses writes at the bound and evicts no key.

#### Scenario: The cache Valkey keeps at most 1536 MiB of data
- **WHEN** the Deployment `valkey` is read from `k8s/llm/valkey.yaml`
- **THEN** its valkey container starts valkey-server with `--maxmemory 1536mb` and `--maxmemory-policy noeviction`, and 1536 MiB is at most three quarters of the container's 2048Mi memory limit

#### Scenario: The run index keeps at most 512 MiB of data
- **WHEN** the Deployment `valkey-runs` is read from `k8s/llm/valkey-runs.yaml`
- **THEN** its valkey container starts valkey-server with `--maxmemory 512mb` and `--maxmemory-policy noeviction`, and 512 MiB is at most three quarters of the container's 768Mi memory limit
