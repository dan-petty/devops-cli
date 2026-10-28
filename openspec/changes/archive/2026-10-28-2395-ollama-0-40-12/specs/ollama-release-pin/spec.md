# ollama-release-pin Specification

## Purpose

The Ollama release that the Ollama tiers run. Every tier and its init container run one release, so every node reads its model store with the same release, and that release runs a multimodal embedding model such as `embeddinggemma-2` on Linux.

## ADDED Requirements

### Requirement: Every Ollama tier runs one Ollama release that runs multimodal embedding models on Linux
Each container and each init container of each DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml` SHALL name one image. The image repository SHALL be `ollama/ollama`, and its tag SHALL be 0.40.4 or later, the first release that runs a multimodal embedding model through `llama-server`.

#### Scenario: Two containers name different images
- **WHEN** a test reads the image of every container and init container of every DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml`
- **THEN** all of them name the same image

#### Scenario: The tiers name a release below the first that runs multimodal embedding models on Linux
- **WHEN** a test reads the image that the tiers name
- **THEN** the image repository is `ollama/ollama`
- **AND** the image tag, read as a version, is 0.40.4 or later
