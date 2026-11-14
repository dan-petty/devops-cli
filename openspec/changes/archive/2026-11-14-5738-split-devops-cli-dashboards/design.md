# Design

## Decisions
- Partitioning Scheme:
  - `devops-cli.json` (UID: `devops-cli-telemetry`, Title: `devops-cli Commands Telemetry`):
    - Rows: `Golden signals: devops commands`, `Breakdown by command`, `Sub-commands`, `GitHub API`.
    - Variables: `$job`, `$command`, `$sub_command`.
  - `roadmap-service-telemetry.json` (UID: `devops-roadmap-service-telemetry`, Title: `Roadmap Service Telemetry`):
    - Rows: `Roadmap Service`, `Alternatives Check`, `Roadmap Job Success`.
    - Variables: `$job`.
  - `devops-ai-rag.json` (UID: `devops-ai-rag`, Title: `devops-cli AI & RAG Operations`):
    - Rows: `RAG Retrieval`, `AI Review Findings Breakdown`, `AI Spend & Economics`, `Planner Tools`.
    - Variables: `$job`.
- Navigation Links:
  - Each dashboard includes top header links (`"type": "link"`) pointing to the other dashboards in the suite.
- Folder Organization:
  - Add `grafana_folder: "DevOps Services"` annotation in `k8s/devops/dashboards/kustomization.yaml`.
  - Update `k8s/monitoring/grafana-values.yaml` sidecar configuration to support `folderAnnotation: grafana_folder` and `provider.foldersFromFilesStructure: true`.
- ConfigMap Provisioning:
  - Keep all five product dashboards (`ai-spend.json`, `devops-ai-rag.json`, `devops-cli.json`, `project-metrics.json`, `roadmap-service-telemetry.json`) in `grafana-devops-cli-dashboards` ConfigMap generator under `k8s/devops/dashboards/kustomization.yaml`. Total payload (~177 KB) remains well under the 262,144-byte annotation ceiling.

## Rejected alternatives
- Single dashboard with collapsed rows: Rejected because loading all queries simultaneously adds latency and clutters the UI.
- Tag-based links only: Rejected because explicit top-bar navigation links provide faster one-click navigation.
