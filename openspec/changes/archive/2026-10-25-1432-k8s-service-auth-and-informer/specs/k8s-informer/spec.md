# Spec Delta

## Purpose

Streams Kubernetes pod events with typed model objects, backoff reconnection, and expired bookmark relisting.

## ADDED Requirements

### Requirement: Informer streams typed pod models directly
The pod informer SHALL invoke the Kubernetes Watch stream with direct function references to `list_namespaced_pod` or `list_pod_for_all_namespaces` without lambda wrappers, yielding typed `V1Pod` objects for downstream event processing.

#### Scenario: Namespaced pod watch yields typed V1Pod
- **WHEN** the informer streams events for a specific namespace
- **THEN** the watch yields events containing `V1Pod` objects and status is resolved via `PodInfo.from_pod`

#### Scenario: All-namespace pod watch yields typed V1Pod
- **WHEN** the informer streams events across all namespaces
- **THEN** the watch yields events containing `V1Pod` objects

### Requirement: Informer reconnect loop applies exponential backoff
The informer worker thread SHALL reconnect failed watch streams using exponential backoff with tenacity, resuming from the latest observed `resourceVersion`.

#### Scenario: Reconnection passes last seen resource version
- **WHEN** a watch stream disconnects or raises an error after observing events with resource version `100`
- **THEN** the subsequent reconnection attempt passes `resource_version="100"`

#### Scenario: Persistent error backs off
- **WHEN** repeated watch stream failures occur
- **THEN** reconnect attempts wait with exponential backoff rather than immediately looping

### Requirement: Informer relists on expired watch bookmarks
When the Kubernetes API server returns HTTP 410 Gone for an expired resource version, the informer SHALL relist pods from the API server to synchronize state and resume watching with the fresh resource version.

#### Scenario: Relist on 410 Gone error
- **WHEN** a watch stream raises an `ApiException` with status 410 Gone
- **THEN** the informer lists pods again, updates the resource version and cache, and restarts streaming
