# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.7` (Completed / Active Release)
1. **Model Curation Pipeline & AI Bill of Materials (`devops scan aibom`)**: CycloneDX 1.5-compliant AI model inventory, `trust_remote_code` AST inspection, and hardware sizing heuristics.
2. **Zero-Allocation AST & Token Stream Parser (`devops_cli.ai.ast_stream`)**: Generator-based streaming symbol parser for rapid AST traversal.
3. **Cross-Encoder Context Re-Ranker (`devops_cli.ai.rag.reranker`)**: Cross-token semantic re-ranking for dense/sparse RAG candidate retrieval.
4. **"Big Decides, Small Types, Big Checks" Synthesis Protocol (`devops_cli.ai.agents.synthesis_protocol`)**: Multi-agent slot offloading and 3-stage synthesis.
5. **High-Performance Streaming Serializers (`devops_cli.output.streaming_serializer`)**: Low-overhead streaming JSON, JSONL, and YAML document generators.

### Upcoming Milestone: `v0.3.0` (Scheduled)
1. **Multi-Region Workstation Mesh & Cluster Federation**: Cross-cluster service discovery and state sync.
2. **Autonomous Self-Healing Agent Pipeline**: Self-diagnostic remediation loops.
3. **Cloud-Native Ephemeral Test Environment Engine**: Dynamic Minikube/Helm ephemeral environments.

---

## 📖 Related Strategic Documents
- **Master Strategic Roadmap**: [`docs/ROADMAP.md`](ROADMAP.md)
- **Active Working Log**: [`docs/LOG.md`](LOG.md)
- **System Architecture**: [`ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Knowledge Base Task Manuals**: [`src/devops_cli/ai/knowledge_base/`](../src/devops_cli/ai/knowledge_base/README.md)
