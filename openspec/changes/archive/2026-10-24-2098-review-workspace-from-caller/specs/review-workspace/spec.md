# Spec Delta

## Purpose

A review and its scanners take the workspace that they read from the command that starts them, never from the working directory of the process.

## ADDED Requirements

### Requirement: A review names a Kube-linter finding by the path of the manifest in its checkout
A review SHALL name the manifest of a Kube-linter finding by its path relative to the working tree that holds the manifest, whatever the directory that the command runs in. The finding SHALL be in the payload of the manifest.

#### Scenario: A review of a manifest in another checkout
- **WHEN** a review of a checkout scans its manifest `k8s/app.yaml`, and the command runs in a directory outside that checkout
- **THEN** the Kube-linter finding of the manifest is named `k8s/app.yaml:Deployment/app`, and it is in the payload of `k8s/app.yaml`

#### Scenario: A manifest that no checkout holds
- **WHEN** Kube-linter reports a manifest that no working tree holds
- **THEN** the finding names the manifest by its file name
