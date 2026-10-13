"""Information foraging and relational epistemic research engine."""

from __future__ import annotations

from devops_cli.ai.research.analogies import (
    AnalogicalPatternRetriever,
    extract_domain,
    multi_vector_clustering,
    render_analogies_markdown,
    render_analogies_table,
)
from devops_cli.ai.research.crawler import ForageCrawler
from devops_cli.ai.research.edges import (
    extract_git_co_changes,
    extract_markdown_links,
    extract_python_imports,
)
from devops_cli.ai.research.marginalia import (
    annotate_file,
    get_marginalia_path,
    read_marginalia,
    write_marginalia,
)
from devops_cli.ai.research.mental_model import (
    MentalModelSynthesizer,
    get_mental_model_path,
    load_mental_model,
    render_mental_model_markdown,
    save_mental_model,
    validate_causal_dag,
)
from devops_cli.ai.research.models import (
    AnalogyReport,
    BacktrackEvent,
    CausalEdge,
    CausalGraph,
    CausalNode,
    ClarifyingQuestion,
    CodeLookupInstruction,
    CrossDomainAnalogy,
    ForageEdge,
    ForageNode,
    ForageTrail,
    InvariantRule,
    KnowledgeGap,
    KnowledgeGapType,
    MarginaliaRecord,
    MarginaliaType,
    MentalModel,
    SocraticInquiryResult,
    StateTransition,
)
from devops_cli.ai.research.socratic import (
    SocraticFormulator,
    render_socratic_markdown,
)

__all__ = [
    "AnalogicalPatternRetriever",
    "AnalogyReport",
    "BacktrackEvent",
    "CausalEdge",
    "CausalGraph",
    "CausalNode",
    "ClarifyingQuestion",
    "CodeLookupInstruction",
    "CrossDomainAnalogy",
    "ForageCrawler",
    "ForageEdge",
    "ForageNode",
    "ForageTrail",
    "InvariantRule",
    "KnowledgeGap",
    "KnowledgeGapType",
    "MarginaliaRecord",
    "MarginaliaType",
    "MentalModel",
    "MentalModelSynthesizer",
    "SocraticFormulator",
    "SocraticInquiryResult",
    "StateTransition",
    "annotate_file",
    "extract_domain",
    "extract_git_co_changes",
    "extract_markdown_links",
    "extract_python_imports",
    "get_marginalia_path",
    "get_mental_model_path",
    "load_mental_model",
    "multi_vector_clustering",
    "read_marginalia",
    "render_analogies_markdown",
    "render_analogies_table",
    "render_mental_model_markdown",
    "render_socratic_markdown",
    "save_mental_model",
    "validate_causal_dag",
    "write_marginalia",
]
