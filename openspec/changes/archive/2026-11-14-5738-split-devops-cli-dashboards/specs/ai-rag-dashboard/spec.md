## ADDED Requirements

### Requirement: The AI and RAG dashboard charts retrieval and review operations
The dashboard `k8s/devops/dashboards/devops-ai-rag.json` SHALL exist with uid `devops-ai-rag` and title `devops-cli AI & RAG Operations`. It SHALL contain rows for "RAG Retrieval", "AI Review Findings Breakdown", "AI Spend & Economics", and "Planner Tools".

#### Scenario: The dashboard is loaded
- **WHEN** the dashboard `devops-ai-rag.json` is read
- **THEN** its uid is `devops-ai-rag`
- **AND** it contains rows "RAG Retrieval", "AI Review Findings Breakdown", "AI Spend & Economics", and "Planner Tools"
- **AND** it defines top-level links pointing to `devops-cli-telemetry` and `devops-roadmap-service-telemetry`
