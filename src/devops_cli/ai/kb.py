"""Built-in DevOps CLI Knowledge Base access module for agent grounding and RAG indexing.

Provides programmatic access to the bundled knowledge base articles across:
- it_domains/topics/ (Core architectural guides)
- it_domains/tools/ (Integrated tool references)
- devops_cli/tasks/ (Operational workflow procedures)
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import tomllib
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from devops_cli.config.constants import (
    CONST_KB_DATE_FORMAT,
    CONST_KB_METADATA_TARGET_SUBDIRS,
    CONST_KB_REFERENCE_PREFIX,
    CONST_KB_SHA_DIGEST_LENGTH,
)

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).resolve().parent / "knowledge_base"
_UV_LOCK_CACHE: dict[str, str] | None = None


def reset_uv_lock_cache() -> None:
    """Clear the cached uv.lock dependency version map."""
    global _UV_LOCK_CACHE
    _UV_LOCK_CACHE = None


def get_knowledge_base_dir() -> Path:
    """Return the absolute path to the bundled knowledge base directory."""
    return _KB_DIR


def knowledge_base_digest(kb_dir: Path | None = None) -> str:
    """Compute SHA-256 digest over sorted relative paths and contents of the bundled knowledge base."""
    import hashlib

    base = (kb_dir or get_knowledge_base_dir()).resolve()
    if not base.is_dir():
        return ""
    hasher = hashlib.sha256()
    files = sorted(p for p in base.rglob("*") if p.is_file() and not p.name.startswith("."))
    for p in files:
        rel_posix = p.relative_to(base).as_posix()
        hasher.update(rel_posix.encode("utf-8"))
        hasher.update(b"\0")
        try:
            hasher.update(p.read_bytes())
        except OSError as exc:
            logger.debug("Failed reading KB file %s for digest: %s", p, exc)
        hasher.update(b"\0")
    return hasher.hexdigest()


def list_knowledge_base_articles(category: str | None = None) -> list[Path]:
    """Discover all markdown articles in the bundled knowledge base.

    Args:
        category: Optional subfolder filter ('devops_cli', 'it_domains',
            'devops_cli/tasks', 'it_domains/topics', 'it_domains/tools').
            If None, returns all articles across all divisions.

    Returns:
        Sorted list of Path objects for matching markdown files.
    """
    kb_dir = get_knowledge_base_dir()
    if not kb_dir.is_dir():
        logger.debug("Knowledge base directory not found at %s", kb_dir)
        return []

    kb_resolved = kb_dir.resolve()
    search_dir = (kb_resolved / category).resolve() if category else kb_resolved
    if not search_dir.is_relative_to(kb_resolved) or not search_dir.exists():
        return []

    articles: list[Path] = []
    for p in search_dir.rglob("*.md"):
        if p.is_file() and p.name != "README.md":
            articles.append(p)

    return sorted(articles)


def load_kb_article(relative_path: str) -> str | None:
    """Load the contents of a specific knowledge base markdown article.

    Args:
        relative_path: Relative path within knowledge_base.

    Returns:
        Article text content, or None if the article is not found or path escapes KB root.
    """
    kb_dir = get_knowledge_base_dir()
    kb_resolved = kb_dir.resolve()
    target = (kb_resolved / relative_path).resolve()

    if not target.is_relative_to(kb_resolved) or not target.is_file():
        return None

    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Failed reading knowledge base article %s: %s", relative_path, exc)
        return None


class KnowledgeBaseStats(BaseModel):
    """Summary statistics of the bundled DevOps CLI knowledge base."""

    model_config = ConfigDict(frozen=True)

    kb_dir: str
    exists: bool
    devops_cli_count: int
    it_domains_count: int
    topics_count: int
    tools_count: int
    tasks_count: int
    total_articles: int


def get_knowledge_base_stats() -> KnowledgeBaseStats:
    """Return summary statistics of the bundled knowledge base."""
    kb_dir = get_knowledge_base_dir()
    devops_cli_articles = list_knowledge_base_articles("devops_cli")
    it_domains_articles = list_knowledge_base_articles("it_domains")
    topics = list_knowledge_base_articles("it_domains/topics")
    tools = list_knowledge_base_articles("it_domains/tools")
    tasks = list_knowledge_base_articles("devops_cli/tasks")

    return KnowledgeBaseStats(
        kb_dir=str(kb_dir),
        exists=kb_dir.is_dir(),
        devops_cli_count=len(devops_cli_articles),
        it_domains_count=len(it_domains_articles),
        topics_count=len(topics),
        tools_count=len(tools),
        tasks_count=len(tasks),
        total_articles=len(devops_cli_articles) + len(it_domains_articles),
    )


# ── Front-Matter & Version-Grounding Metadata Models (#1149) ─────────────────


def _is_valid_spec_syntax(spec: str) -> bool:
    """Verify that an applies_to specifier matches a supported prefix/grammar."""
    clean = spec.strip()
    if clean.startswith("python"):
        return len(clean) > 6 and any(
            clean[6:].startswith(op) for op in (">=", "<=", "==", "!=", "~=", ">", "<", "@")
        )
    if clean.startswith("tool:") and "@" in clean:
        return len(clean.split("@", 1)[0]) > 5
    if clean.startswith("pkg:") and "@" in clean and "/" in clean:
        return len(clean.split("@", 1)[0]) > 4
    if clean.startswith("k8s"):
        return "@" in clean or len(clean) > 3
    return False


class KbFrontMatter(BaseModel):
    """YAML front-matter specification for a knowledge base manual (#1149)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applies_to: tuple[str, ...] = Field(min_length=1)
    sources: tuple[str, ...] = Field(min_length=1)
    reviewed: str
    tags: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("reviewed")
    @classmethod
    def validate_reviewed_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, CONST_KB_DATE_FORMAT)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"reviewed date must match {CONST_KB_DATE_FORMAT}: {v}") from exc
        return v

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("sources list cannot be empty")
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"source URL must start with http:// or https://: {url}")
        return v

    @field_validator("applies_to")
    @classmethod
    def validate_applies_to(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("applies_to list cannot be empty")
        for spec in v:
            if not _is_valid_spec_syntax(spec):
                raise ValueError(f"invalid applies_to specifier syntax: {spec}")
        return v


class MatchedManual(BaseModel):
    """A knowledge base manual matched to the active project environment (#1149)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    key: str
    content: str
    tools: tuple[str, ...] = Field(default_factory=tuple)
    topics: tuple[str, ...] = Field(default_factory=tuple)
    tags: tuple[str, ...] = Field(default_factory=tuple)
    sha: str


class DriftManual(BaseModel):
    """A knowledge base manual in drift (mismatched version, missing dependency, or undated) (#1149)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    reason: str


def parse_manual_front_matter(content: str) -> tuple[KbFrontMatter | None, str, str | None]:
    """Parse YAML front-matter from a manual's content.

    Returns:
        (front_matter, body, error_reason)
    """
    if not content.startswith("---\n"):
        return None, content, "missing front-matter (file does not begin with '---')"
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return None, content, "malformed front-matter (unclosed '---' delimiter)"
    raw_yaml = parts[1]
    body = parts[2].lstrip("\n")
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        return None, body, f"YAML parse error: {exc}"
    if not isinstance(data, dict):
        return None, body, "front-matter must be a YAML mapping"
    try:
        fm = KbFrontMatter.model_validate(data)
        return fm, body, None
    except ValidationError as exc:
        msg = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return None, body, f"invalid front-matter schema: {msg}"


def _lookup_uv_lock_version(name: str) -> list[str]:
    """Look up a package version from the root uv.lock file if available."""
    global _UV_LOCK_CACHE
    if _UV_LOCK_CACHE is None:
        _UV_LOCK_CACHE = {}
        uv_path = Path("uv.lock")
        if uv_path.is_file():
            try:
                data = tomllib.loads(uv_path.read_text(encoding="utf-8"))
                for pkg in data.get("package", []):
                    if p_name := pkg.get("name"):
                        _UV_LOCK_CACHE[p_name.lower().replace("_", "-")] = pkg.get("version", "")
            except (OSError, tomllib.TOMLDecodeError) as exc:
                logger.debug("Failed reading uv.lock for KB version lookup: %s", exc)
    ver = _UV_LOCK_CACHE.get(name.lower().replace("_", "-"))
    return [ver] if ver else []


def _version_matches_pattern(ver: str, pattern: str) -> bool:
    """Check if a concrete version matches a specifier pattern (exact, wildcard, or SpecifierSet)."""
    clean_ver = ver.lstrip("v").strip()
    clean_pat = pattern.lstrip("v").strip()
    if clean_pat.startswith((">=", "<=", "==", "!=", "~=", ">", "<")):
        try:
            return SpecifierSet(clean_pat).contains(clean_ver)
        except (InvalidSpecifier, InvalidVersion) as exc:
            logger.debug(
                "Invalid specifier pattern '%s' for version '%s': %s", clean_pat, clean_ver, exc
            )
    if fnmatch.fnmatch(clean_ver, clean_pat):
        return True
    if clean_pat.endswith(".*"):
        prefix = clean_pat[:-2]
        return clean_ver == prefix or clean_ver.startswith(f"{prefix}.")
    return clean_ver == clean_pat or clean_ver.startswith(f"{clean_pat}.")


def _match_python_spec(spec: str, python_pin: str, language_floor: str) -> tuple[bool, str]:
    spec_part = spec[6:].strip()
    if spec_part.startswith("@"):
        spec_part = f"=={spec_part[1:]}"
    effective_python = python_pin or language_floor.removeprefix("py").strip()
    if not effective_python:
        return False, "python version not configured in environment"
    try:
        spec_set = SpecifierSet(spec_part)
        pin_ver = Version(effective_python)
        if spec_set.contains(pin_ver):
            return True, ""
        return False, f"mismatched python: requires {spec}, found {effective_python}"
    except (InvalidSpecifier, InvalidVersion) as exc:
        return False, f"invalid python specifier {spec}: {exc}"


def _match_tool_spec(spec: str, tool_versions: Mapping[str, str]) -> tuple[bool, str]:
    body = spec[5:]
    if "@" not in body:
        return False, f"malformed tool specifier: {spec}"
    name, pattern = body.split("@", 1)
    norm_name = name.lower().replace("_", "-")
    tv = tool_versions.get(norm_name) or tool_versions.get(name.lower())
    if not tv:
        compact = norm_name.replace("-", "")
        for k, v in tool_versions.items():
            if k.replace("-", "") == compact:
                tv = v
                break
    if not tv:
        return False, f"tool:{name} not found in tools.lock or environment"
    if _version_matches_pattern(tv, pattern):
        return True, ""
    return False, f"mismatched tool {name}: requires {pattern}, found {tv}"


def _extract_candidate_versions(
    name: str,
    full_purl: str,
    locked_packages: Mapping[str, Sequence[str]],
    cdx_inventory: Mapping[str, Any],
) -> list[str]:
    """Collect candidate versions for a package from locked packages, CycloneDX, and uv.lock."""
    candidate_versions: list[str] = []
    for k, v in locked_packages.items():
        k_norm = k.lower().replace("_", "-")
        if k_norm in (name, full_purl) or k_norm.startswith(f"{full_purl}@"):
            if isinstance(v, (list, tuple)):
                candidate_versions.extend(str(item) for item in v)
            elif isinstance(v, str):
                candidate_versions.append(v)

    if not candidate_versions and cdx_inventory:
        for comp in cdx_inventory.get("components", []):
            comp_name = comp.get("name", "").lower().replace("_", "-")
            comp_purl = comp.get("purl", "").lower()
            if comp_name == name or comp_purl.startswith(full_purl):
                if ver := comp.get("version"):
                    candidate_versions.append(str(ver))

    if not candidate_versions:
        candidate_versions.extend(_lookup_uv_lock_version(name))

    return candidate_versions


def _match_package_spec(
    spec: str,
    locked_packages: Mapping[str, Sequence[str]],
    cdx_inventory: Mapping[str, Any],
) -> tuple[bool, str]:
    body = spec[4:]
    if "@" not in body or "/" not in body:
        return False, f"malformed pkg specifier: {spec}"
    pkg_path, pattern = body.split("@", 1)
    name = pkg_path.split("/")[-1].lower().replace("_", "-")
    full_purl = f"pkg:{pkg_path.lower()}"

    candidate_versions = _extract_candidate_versions(
        name, full_purl, locked_packages, cdx_inventory
    )
    if not candidate_versions:
        return False, f"pkg:{pkg_path} not found in locked inventory"

    for pv in candidate_versions:
        if _version_matches_pattern(pv, pattern):
            return True, ""
    return False, f"mismatched pkg {pkg_path}: requires {pattern}, found {candidate_versions[0]}"


def _match_k8s_spec(spec: str, kubernetes_version: str | None) -> tuple[bool, str]:
    pattern = spec.split("@", 1)[1] if "@" in spec else spec.removeprefix("k8s")
    pattern = pattern.lstrip("@").strip()
    if not kubernetes_version:
        return False, "kubernetes_version not configured in review"
    kv = kubernetes_version.lstrip("v").strip()
    if _version_matches_pattern(kv, pattern):
        return True, ""
    return False, f"mismatched kubernetes: requires {pattern}, found {kubernetes_version}"


def _evaluate_single_spec(
    spec: str,
    tool_versions: Mapping[str, str],
    locked_packages: Mapping[str, Sequence[str]],
    cdx_inventory: Mapping[str, Any],
    language_floor: str,
    python_pin: str,
    kubernetes_version: str | None,
) -> tuple[bool, str]:
    if spec.startswith("python"):
        return _match_python_spec(spec, python_pin, language_floor)
    if spec.startswith("tool:"):
        return _match_tool_spec(spec, tool_versions)
    if spec.startswith("pkg:"):
        return _match_package_spec(spec, locked_packages, cdx_inventory)
    if spec.startswith("k8s"):
        return _match_k8s_spec(spec, kubernetes_version)
    return False, f"unsupported applies_to specifier: {spec}"


def _evaluate_applies_to(
    fm: KbFrontMatter,
    tool_versions: Mapping[str, str],
    locked_packages: Mapping[str, Sequence[str]],
    cdx_inventory: Mapping[str, Any],
    language_floor: str,
    python_pin: str,
    kubernetes_version: str | None,
) -> tuple[bool, str]:
    for spec in fm.applies_to:
        ok, reason = _evaluate_single_spec(
            spec,
            tool_versions,
            locked_packages,
            cdx_inventory,
            language_floor,
            python_pin,
            kubernetes_version,
        )
        if not ok:
            return False, reason
    return True, ""


def _extract_manual_tags(
    rel_path: str,
    fm: KbFrontMatter,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Extract (tools, topics, all_tags) for a knowledge base manual."""
    tools: set[str] = set()
    topics: set[str] = set()
    tags: set[str] = set(fm.tags)

    stem = Path(rel_path).stem.lower()
    parent = Path(rel_path).parent.name.lower()

    if parent == "tools":
        tools.add(stem)
    elif parent == "topics":
        topics.add(stem)
    elif parent == "libraries":
        tools.add(stem)

    for item in fm.applies_to:
        if item.startswith("tool:"):
            tname = item[5:].split("@")[0].lower()
            tools.add(tname)
        elif item.startswith("pkg:"):
            pname = item[4:].split("@")[0].split("/")[-1].lower()
            tools.add(pname)
        elif item.startswith("k8s"):
            tools.add("k8s")
            tools.add("kubernetes")
            tools.add("kubectl")

    for t in tools:
        tags.add(t)
    for top in topics:
        tags.add(top)

    return tuple(sorted(tools)), tuple(sorted(topics)), tuple(sorted(tags))


class _MatchContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    tool_versions: dict[str, str]
    locked_packages: dict[str, list[str]]
    cyclonedx_inventory: dict[str, Any]
    language_floor: str
    python_pin: str
    kubernetes_version: str


def _apply_environment_facts(
    env: Any,
    tool_versions: dict[str, str],
    locked_packages: dict[str, list[str]],
    cdx: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Extract environment overrides and populate tool versions and packages."""
    for k, v in getattr(env, "tool_versions", {}).items():
        tool_versions.setdefault(k.lower(), v)
    for k, v in getattr(env, "locked_packages", {}).items():
        locked_packages.setdefault(k, list(v))
    if not cdx and hasattr(env, "cyclonedx_inventory"):
        cdx.update(getattr(env, "cyclonedx_inventory", None) or {})
    lang_floor = getattr(env, "language_floor", None)
    python_pin = getattr(env, "python_pin", None)
    k8s = getattr(env, "kubernetes_version", None)
    return lang_floor, python_pin, k8s


def _apply_tools_lock(tools_lock: Any | None, tool_versions: dict[str, str]) -> str | None:
    """Load tools.lock facts and populate tool versions."""
    if tools_lock is None:
        try:
            from devops_cli.tools_lock import load_tools_lock

            tools_lock = load_tools_lock()
        except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
            logger.debug("Failed loading tools.lock: %s", exc)
            tools_lock = None
    if tools_lock is None:
        return None
    if hasattr(tools_lock, "tools"):
        for name, tool in tools_lock.tools().items():
            tool_versions.setdefault(name.lower(), tool.version)
    return getattr(tools_lock, "python_version", None)


def _resolve_matching_context(
    tools_lock: Any | None,
    environment: Any | None,
    kubernetes_version: str | None,
    cyclonedx_inventory: dict[str, Any] | None,
    locked_packages: Mapping[str, Sequence[str]] | None,
    language_floor: str | None,
    python_pin: str | None,
    tool_versions: Mapping[str, str] | None,
) -> _MatchContext:
    eff_tool_versions: dict[str, str] = dict(tool_versions or {})
    eff_locked_packages: dict[str, list[str]] = {
        k: list(v) for k, v in (locked_packages or {}).items()
    }
    eff_cdx: dict[str, Any] = dict(cyclonedx_inventory or {})
    eff_lang_floor: str = language_floor or "py314"
    eff_python_pin: str = python_pin or "3.14"
    eff_k8s: str | None = kubernetes_version

    if environment is not None:
        env_floor, env_pin, env_k8s = _apply_environment_facts(
            environment, eff_tool_versions, eff_locked_packages, eff_cdx
        )
        eff_lang_floor = env_floor or eff_lang_floor
        eff_python_pin = env_pin or eff_python_pin
        eff_k8s = eff_k8s or env_k8s

    lock_pin = _apply_tools_lock(tools_lock, eff_tool_versions)
    eff_python_pin = eff_python_pin or lock_pin or "3.14"
    eff_k8s = eff_k8s or "v1.31.0"

    return _MatchContext(
        tool_versions=eff_tool_versions,
        locked_packages=eff_locked_packages,
        cyclonedx_inventory=eff_cdx,
        language_floor=eff_lang_floor,
        python_pin=eff_python_pin,
        kubernetes_version=eff_k8s,
    )


def _process_manual_file(
    md_file: Path,
    base_dir: Path,
    ctx: _MatchContext,
) -> tuple[MatchedManual | None, DriftManual | None]:
    rel_path = md_file.relative_to(base_dir).as_posix()
    try:
        content = md_file.read_text(encoding="utf-8")
    except OSError as exc:
        return None, DriftManual(path=rel_path, reason=f"read error: {exc}")

    fm, body, error_reason = parse_manual_front_matter(content)
    if fm is None:
        return None, DriftManual(path=rel_path, reason=error_reason or "undated manual")

    is_match, reason = _evaluate_applies_to(
        fm,
        ctx.tool_versions,
        ctx.locked_packages,
        ctx.cyclonedx_inventory,
        ctx.language_floor,
        ctx.python_pin,
        ctx.kubernetes_version,
    )
    if not is_match:
        return None, DriftManual(path=rel_path, reason=reason)

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:CONST_KB_SHA_DIGEST_LENGTH]
    key = f"{CONST_KB_REFERENCE_PREFIX}{rel_path}@{sha}"
    tools, topics, tags = _extract_manual_tags(rel_path, fm)
    matched = MatchedManual(
        path=rel_path,
        key=key,
        content=body,
        tools=tools,
        topics=topics,
        tags=tags,
        sha=sha,
    )
    return matched, None


def load_matched_kb_manuals(
    *,
    kb_dir: Path | None = None,
    tools_lock: Any | None = None,
    environment: Any | None = None,
    kubernetes_version: str | None = None,
    cyclonedx_inventory: dict[str, Any] | None = None,
    locked_packages: Mapping[str, Sequence[str]] | None = None,
    language_floor: str | None = None,
    python_pin: str | None = None,
    tool_versions: Mapping[str, str] | None = None,
) -> tuple[list[MatchedManual], list[DriftManual]]:
    """Match KB manuals against tools.lock, locked inventory, language floor and kubernetes_version (#1149)."""
    base_dir = (kb_dir or get_knowledge_base_dir()).resolve()
    ctx = _resolve_matching_context(
        tools_lock,
        environment,
        kubernetes_version,
        cyclonedx_inventory,
        locked_packages,
        language_floor,
        python_pin,
        tool_versions,
    )
    matched: list[MatchedManual] = []
    drift: list[DriftManual] = []

    for sub in CONST_KB_METADATA_TARGET_SUBDIRS:
        sub_dir = (base_dir / sub).resolve()
        if not sub_dir.is_dir():
            continue
        for md_file in sorted(sub_dir.rglob("*.md")):
            if md_file.name == "README.md":
                continue
            item, drift_item = _process_manual_file(md_file, base_dir, ctx)
            if item is not None:
                matched.append(item)
            elif drift_item is not None:
                drift.append(drift_item)

    return matched, drift


def _extract_group_tool_keys(group: Any) -> set[str]:
    keys: set[str] = set()
    findings = getattr(group, "findings", ())
    for f in findings:
        tool = getattr(f, "tool", "").lower().replace("_", "-")
        if tool:
            keys.add(tool)
            keys.add(tool.replace("-", ""))
        rule_id = getattr(f, "rule_id", "")
        if rule_id:
            keys.add(rule_id.lower())
        props = getattr(f, "properties", {})
        if isinstance(props, dict) and "rule_family" in props:
            keys.add(str(props["rule_family"]).lower())
    return keys


def _is_k8s_group(group: Any) -> bool:
    kind = getattr(group, "kind", None)
    if kind and str(kind).lower() == "k8s_object":
        return True
    findings = getattr(group, "findings", ())
    for f in findings:
        tool = getattr(f, "tool", "").lower()
        if tool in (
            "kube-linter",
            "kubelinter",
            "popeye",
            "pluto",
            "checkov",
            "kustomize",
            "kubectl",
        ):
            return True
        loc = getattr(f, "logical_location", "") or ""
        path = getattr(f, "path", "") or ""
        if path.endswith((".yaml", ".yml")) and "/" in loc and not loc.startswith("pkg:"):
            return True
    return False


def _is_python_group(group: Any) -> bool:
    findings = getattr(group, "findings", ())
    for f in findings:
        path = getattr(f, "path", "") or ""
        tool = getattr(f, "tool", "").lower()
        if path.endswith((".py", ".pyi")) or tool in ("bandit", "ruff", "mypy", "pytest"):
            return True
    return False


def filter_kb_manuals_for_group(
    group: Any,
    matched_manuals: Sequence[MatchedManual] | Mapping[str, str],
) -> dict[str, str]:
    """Filter matched KB manuals to those relevant to the group's producing tools and rule families (#1149)."""
    if isinstance(matched_manuals, Mapping):
        if not matched_manuals:
            return {}
        has_kb_sub = any(
            sub in k for k in matched_manuals for sub in ("devops_cli/", "it_domains/")
        )
        if not has_kb_sub:
            return dict(matched_manuals)
        group_tools = _extract_group_tool_keys(group)
        filtered: dict[str, str] = {}
        for k, v in matched_manuals.items():
            k_lower = k.lower()
            if any(t in k_lower for t in group_tools):
                filtered[k] = v
        return filtered or dict(matched_manuals)

    group_tools = _extract_group_tool_keys(group)
    group_is_k8s = _is_k8s_group(group)
    group_is_py = _is_python_group(group)

    result: dict[str, str] = {}
    for m in matched_manuals:
        if any(t in group_tools for t in m.tools) or any(t in group_tools for t in m.tags):
            result[m.key] = m.content
            continue
        if group_is_k8s and any(
            k in m.tools or k in m.tags for k in ("k8s", "kubernetes", "kubectl")
        ):
            result[m.key] = m.content
            continue
        if group_is_py and "modern_python_runtime_and_ecosystem" in m.topics:
            result[m.key] = m.content
            continue

    return result


__all__ = [
    "DriftManual",
    "KbFrontMatter",
    "KnowledgeBaseStats",
    "MatchedManual",
    "filter_kb_manuals_for_group",
    "get_knowledge_base_dir",
    "get_knowledge_base_stats",
    "knowledge_base_digest",
    "list_knowledge_base_articles",
    "load_kb_article",
    "load_matched_kb_manuals",
    "parse_manual_front_matter",
    "reset_uv_lock_cache",
]
