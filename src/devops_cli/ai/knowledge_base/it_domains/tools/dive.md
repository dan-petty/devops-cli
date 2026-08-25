# Dive Tool Reference Manual

## 1. Overview & Operational Mandate
Dive is a container image exploration and layer analysis tool designed to inspect Docker images, discover layer contents, and identify wasted space caused by redundant file duplication or unoptimized build steps.

In `devops-cli`, Dive is integrated via `devops docker analyze-layers` and `run_dive_analysis()` under `src/devops_cli/security/dive.py`.

## 2. Key Capabilities
- **Layer-by-Layer Inspection**: Analyzes file additions, modifications, and deletions across container layers.
- **Image Efficiency Scoring**: Calculates an image efficiency percentage based on wasted bytes vs total image size.
- **CI Integration**: Enables automated container image size gating in build pipelines.

## 3. CLI Invocations
```bash
# Analyze image layers and efficiency score
devops docker analyze-layers my-app:latest

# Output structured efficiency metrics as JSON
devops docker analyze-layers ghcr.io/dan-petty/devops-cli/devcontainer:latest --json
```

## 4. Native Persona Tool Registration
- **Registered Tool**: `docker_analyze_layers`
- **Personas**: `architect`, `qa`
