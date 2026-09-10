"""Pydantic v2 data models representing library API contracts, symbol signatures, and ingested docs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParameterSignature(BaseModel):
    """Represents a single function or method parameter."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Parameter name identifier")
    annotation: str = Field(default="Any", description="Type annotation string representation")
    default: str | None = Field(
        default=None, description="Default value string representation if provided"
    )
    has_default: bool = Field(default=False, description="True if a default value is specified")
    kind: str = Field(
        default="POSITIONAL_OR_KEYWORD",
        description="Parameter calling kind (POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD)",
    )
    is_required: bool = Field(
        default=True, description="True if parameter is required (no default and not variadic)"
    )


class FunctionSignature(BaseModel):
    """Represents a standalone function or class method signature."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Function or method name")
    qualname: str = Field(description="Fully-qualified module path and name")
    parameters: list[ParameterSignature] = Field(
        default_factory=list, description="Ordered list of parameters"
    )
    return_annotation: str = Field(
        default="Any", description="Return type annotation string representation"
    )
    docstring: str | None = Field(default=None, description="Docstring summary description")
    is_async: bool = Field(
        default=False, description="True if function is an asynchronous coroutine"
    )
    is_generator: bool = Field(
        default=False, description="True if function yields generator values"
    )
    is_deprecated: bool = Field(default=False, description="True if function is marked deprecated")
    deprecation_message: str | None = Field(
        default=None, description="Deprecation warning message if applicable"
    )


class ClassSignature(BaseModel):
    """Represents a class definition, inheritance hierarchy, and public methods."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Class name")
    qualname: str = Field(description="Fully-qualified class path")
    bases: list[str] = Field(default_factory=list, description="Direct base class names")
    docstring: str | None = Field(default=None, description="Class-level docstring")
    methods: dict[str, FunctionSignature] = Field(
        default_factory=dict, description="Public method signatures"
    )
    properties: list[str] = Field(default_factory=list, description="Exposed property names")


class ModuleContract(BaseModel):
    """Represents public symbols and signatures extracted from a Python module."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Full module name")
    docstring: str | None = Field(default=None, description="Module-level docstring")
    all_exports: list[str] = Field(
        default_factory=list, description="Explicit symbols declared in __all__"
    )
    functions: dict[str, FunctionSignature] = Field(
        default_factory=dict, description="Exported standalone functions"
    )
    classes: dict[str, ClassSignature] = Field(
        default_factory=dict, description="Exported class definitions"
    )
    constants: dict[str, str] = Field(
        default_factory=dict, description="Public constants and literals"
    )
    submodules: list[str] = Field(default_factory=list, description="Discovered submodule names")


class LibraryContract(BaseModel):
    """Top-level contract representing an entire package's public API surface."""

    model_config = ConfigDict(frozen=True)

    package_name: str = Field(description="Installed package distribution name")
    version: str = Field(description="Installed package semver version")
    timestamp: str = Field(description="Extraction timestamp in ISO-8601 UTC format")
    modules: dict[str, ModuleContract] = Field(
        default_factory=dict, description="Extracted module contracts"
    )
    symbols_index: dict[str, str] = Field(
        default_factory=dict,
        description="Fast lookup index mapping qualified symbol names to symbol kind (class, function, method)",
    )
    total_modules: int = Field(default=0, description="Total number of introspected modules")
    total_functions: int = Field(
        default=0, description="Total number of extracted functions and methods"
    )
    total_classes: int = Field(default=0, description="Total number of extracted classes")


class DocChunk(BaseModel):
    """A clean markdown reference chunk extracted from documentation."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(description="Unique deterministic chunk identifier")
    source: str = Field(description="Source file path or origin URL")
    headings: list[str] = Field(default_factory=list, description="Heading hierarchy breadcrumbs")
    title: str = Field(description="Primary section title")
    content: str = Field(description="Cleaned markdown content section")
    token_estimate: int = Field(default=0, description="Estimated token count")
    tags: list[str] = Field(default_factory=list, description="Categorical tags for filtering")


class IngestDocResult(BaseModel):
    """Result of a documentation ingestion operation."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="Origin source URL or local directory path")
    is_remote: bool = Field(description="True if documentation was crawled over HTTP/HTTPS")
    total_pages: int = Field(description="Total distinct document pages processed")
    total_chunks: int = Field(description="Total chunks extracted and stored")
    output_dir: str = Field(description="Filesystem directory where chunks were saved")
    chunk_files: list[str] = Field(
        default_factory=list, description="List of generated chunk filenames"
    )


class LibrarySearchResult(BaseModel):
    """Semantic or exact search result returned from the library vector and symbol store."""

    model_config = ConfigDict(frozen=True)

    symbol_name: str = Field(description="Fully qualified symbol name or document section title")
    package_name: str = Field(description="Origin library package name")
    version: str = Field(default="", description="Package version string")
    kind: str = Field(
        default="function", description="Symbol kind: function, class, method, or doc"
    )
    signature_text: str = Field(default="", description="Formatted parameter and return signature")
    docstring: str | None = Field(default=None, description="Docstring or section content summary")
    score: float = Field(default=0.0, description="Relevance similarity score (0.0 - 1.0)")
    source: str = Field(default="library_contract", description="Origin source descriptor")
