# ollama-image-pin Specification

## Purpose
The Ollama image that every tier in `k8s/llm/profiles/` runs. All tiers run one image, named by tag and digest, so a re-pushed tag cannot change what they run.

## Requirements

### Requirement: Every Ollama container pins the image by tag and digest
Each container and init container of the Ollama tiers in `k8s/llm/profiles/ollama-profiles.yaml` and `k8s/llm/profiles/tier-templates/ollama-48gib-slow.yaml` SHALL run the same image, `ollama/ollama:<tag>@sha256:<digest>`. The digest fixes the exact image, so a re-pushed tag cannot change what the tiers run.

#### Scenario: A tier names its image by tag only
- **WHEN** a test reads the images of the Ollama tiers
- **THEN** every image has the form `ollama/ollama:<tag>@sha256:<64 hex digits>`
- **AND** all tiers use one image
- **AND** the tag, read as a version, is at least the first release that serves embeddings with `llama-server`
