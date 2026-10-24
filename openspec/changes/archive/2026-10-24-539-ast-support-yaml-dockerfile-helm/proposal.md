# Proposal

## Why

Issue #539 shows that Kubernetes manifests, Helm templates and Dockerfiles yield no AST symbols in devops-cli. Repository maps remain empty for Docker samples and show only incidental code for Helm and Kubernetes samples.

## What Changes

This change adds polyglot AST symbol extraction for Kubernetes manifests, Helm templates and Dockerfiles:
- Add `tree-sitter-yaml` to parse YAML source files and extract Kubernetes resource kind and name symbols.
- Add `tree-sitter-dockerfile` to parse Dockerfiles and extract stage aliases and FROM image symbols.
- Add Helm template block parsing for `.tpl` files to extract named templates from `define` blocks.
- Extend language detection and file mapping to recognize `.yaml`, `.yml`, `.tpl` and Dockerfile paths.
- Update sample validation and multilingual repository maps to display symbols for these categories.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `ast-support`: Extract polyglot AST symbols from Kubernetes manifests, Helm templates and Dockerfiles.

### Modified Capabilities
None.

## Impact

- Runtime dependencies: Adds `tree-sitter-yaml==0.7.2` and `tree-sitter-dockerfile==0.2.0` in `pyproject.toml`.
- AST engine: Updates `devops_cli.ai.ast.engine` with grammar definitions, file extension mappings and symbol extraction logic.
- Repository maps: Updates `devops_cli.ai.repomap` and `devops_cli.ai.ast.graph` to discover and map Dockerfile, YAML and Helm template files.
- Reviews: Eliminates missing AST coverage warnings in `devops review samples validate` for Kubernetes, Helm and Dockerfile samples.

## Feasibility

I confirmed the premise against the real system:
- `uv run devops review samples validate --category kubernetes-helm --category dockerfile` reported missing AST support for 41 YAML files, 1 `.tpl` file and 5 Dockerfiles.
- PyPI provides official packages `tree-sitter-yaml==0.7.2` and `tree-sitter-dockerfile==0.2.0`, which load with `tree-sitter==0.26.0`.
- Helm `.tpl` templates define reusable templates through `define` blocks, and a balanced block parser extracts each template name and span offline.
- Tested parsing against all 41 sample YAML files in `kubernetes-examples` and `prometheus-node-exporter-chart`, confirming kind and name symbol extraction.

## Existing Tool Considered

`tree-sitter-yaml` and `tree-sitter-dockerfile` provide native tree-sitter grammars for YAML and Dockerfiles. Helm templates have no tree-sitter grammar package on PyPI. Implementing the Helm template block parser internally requires approximately 40 lines of code, 5,000 tokens of agent context and 10 minutes of elapsed time. This change deletes no existing code.
