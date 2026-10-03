"""Common AI Hallucinations catalog, similarity matching, and the claims people disproved.

The builtin catalog ships curated recurring AI false positives (such as Python 3.14 PEP 758
bracketless except clauses, masked secret placeholders, and synthetic test mock credentials),
each matched by signature and confirmed against the target source before it invalidates.

The learned catalog, in the data directory, holds only what a person's INVALIDATED verdict
judged: one claim about one piece of code, which a later review suppresses exactly (#950). The
machine teaches it nothing: entries the deterministic checks once taught it paired common words
such as `exception` and `handling`, and would have invalidated real defects had their ground
truth ever passed. They are purged from the ledger on its first load.

SAFETY INVARIANT:
No common English words (such as 'secret', 'token', 'test', 'error', 'syntax', 'code') may
be used to flag findings as hallucinations. Real defects and security vulnerabilities must NEVER
be invalidated without concrete ground-truth proof in the target source file.
"""

from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import logging
import os
import re
import warnings
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devops_cli.ai.review.judged_claims import JudgedClaim, cited_code, judged_claim, project_of
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_HALLUCINATION_FORBIDDEN_WORDS,
    CONST_HALLUCINATIONS_FILE_NAME,
    CONST_HALLUCINATIONS_LOCK_SUFFIX,
    CONST_JUDGED_CLAIM_ID_PREFIX,
    CONST_JUDGED_CLAIM_SOURCE,
)
from devops_cli.config.defaults import (
    DEFAULT_HALLUCINATION_EXEMPLAR_CHARS,
    DEFAULT_HALLUCINATION_EXEMPLAR_COUNT,
    DEFAULT_HALLUCINATIONS_FILE_PATH,
)
from devops_cli.core.repo import find_worktree_root
from devops_cli.exceptions.validation import ValidationError as InvalidEntryError
from devops_cli.security.sanitizer import mask_secrets, sanitize_prompt_boundary_tags

logger = logging.getLogger(__name__)

# Common generic words that MUST NEVER contribute to hallucination classification
_FORBIDDEN_COMMON_WORDS: frozenset[str] = CONST_HALLUCINATION_FORBIDDEN_WORDS


class HallucinationCategory(StrEnum):
    """Classification of common AI review hallucinations and false-positive patterns."""

    SYNTAX_GRAMMAR = "syntax_grammar"
    SECRET_SCANNING = "secret_scanning"
    DEPENDENCY_ECOSYSTEM = "dependency_ecosystem"
    TEST_MOCKS = "test_mocks"
    DOCUMENTATION_CONTEXT = "documentation_context"
    MUTABLE_DEFAULTS = "mutable_defaults"
    BOUNDARY_ERRORS = "boundary_errors"
    GENERAL = "general"


class CommonHallucinationEntry(BaseModel):
    """Definition and metadata for a recurring AI review hallucination pattern."""

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    category: HallucinationCategory
    description: str
    signature_patterns: list[str] = Field(default_factory=list)
    pattern_keywords: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default_factory=list)
    resolution: str
    occurrence_count: int = 1
    last_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    # "builtin", shipped with the tool, or "person": a person's INVALIDATED verdict judged it,
    # and `occurrence_count` counts the verdicts that did.
    source: str = "builtin"
    # The claim a person's verdict suppresses; set on every learned entry and on no builtin one.
    judged: JudgedClaim | None = None


class HallucinationMatch(BaseModel):
    """Result of evaluating a Finding against a known CommonHallucinationEntry."""

    model_config = ConfigDict(frozen=True)

    hallucination: CommonHallucinationEntry
    similarity_score: float
    matched_keywords: list[str] = Field(default_factory=list)
    reason: str


# ── Built-in Catalog of Common Hallucinations ────────────────────────────────


_BUILTIN_HALLUCINATIONS_FILE = Path(__file__).resolve().parent / "common_hallucinations.json"


def _build_builtin_hallucinations() -> list[CommonHallucinationEntry]:
    """Load the baseline verified common hallucinations catalog from its JSON file.

    Entries are validated individually: a single malformed record must never discard the
    whole baseline, because silently falling back to an empty builtin catalog leaves
    verification matching no shipped entry, which degrades it without any visible signal.
    """
    if not (_BUILTIN_HALLUCINATIONS_FILE.exists() and _BUILTIN_HALLUCINATIONS_FILE.is_file()):
        logger.warning(
            "Builtin hallucinations catalog missing at %s; verification will match no "
            "shipped entry",
            _BUILTIN_HALLUCINATIONS_FILE,
        )
        return []

    try:
        data = json.loads(_BUILTIN_HALLUCINATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed reading builtin hallucinations from %s: %s", _BUILTIN_HALLUCINATIONS_FILE, exc
        )
        return []

    if not isinstance(data, list):
        logger.warning(
            "Builtin hallucinations catalog at %s is not a JSON list", _BUILTIN_HALLUCINATIONS_FILE
        )
        return []

    entries: list[CommonHallucinationEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(CommonHallucinationEntry.model_validate(item))
        except ValidationError as exc:
            logger.warning(
                "Skipping malformed builtin hallucination entry %r: %s",
                item.get("id", "<unknown>"),
                exc,
            )
    return entries


# ── File Path & Storage Helpers ──────────────────────────────────────────────


def get_common_hallucinations_file_path() -> Path:
    """Resolve the persistent storage file path for common hallucinations catalog.

    Respects DEVOPS_CLI_DATA_DIR environment override; a relative location resolves under the
    review data root, so every worktree and command learns into and reads one catalog, and a
    review started in another repository never reads one that repository commits
    (`resolve_review_data_path`, #972).
    """
    from devops_cli.core.repo import resolve_review_data_path

    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    target = resolve_review_data_path(
        Path(env_dir) / CONST_HALLUCINATIONS_FILE_NAME
        if env_dir
        else DEFAULT_HALLUCINATIONS_FILE_PATH
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


# A claim that a file does not parse. The word "syntax" alone is not one: "f-string syntax
# interpolates user input into SQL" and "bare `except` clause" describe code that parses.
SYNTAX_CLAIM = re.compile(
    r"\bsyntax\s*error\b|\bsyntaxerror\b|\binvalid\s+(?:python\s+)?syntax\b|\bparse\s+error\b"
    r"|\b(?:fails?|failed|unable)\s+to\s+(?:parse|compile)\b|\bpython\s*2\s+(?:syntax|style)\b"
    r"|\bdeprecated\s+syntax\b",
    re.IGNORECASE,
)

# A CWE-400 finding about input the program does not control; reading it without a bound is a
# real defect, whatever the call looks like.
_UNTRUSTED_INPUT_CLAIM = re.compile(
    r"\b(?:user|attacker|untrusted|external|upload\w*|request|client|remote|tenant)\b",
    re.IGNORECASE,
)


def _builtin_ids() -> frozenset[str]:
    return frozenset(b.id for b in _build_builtin_hallucinations())


def load_common_hallucinations(
    target_file: Path | None = None, include_builtin: bool = True
) -> list[CommonHallucinationEntry]:
    """The builtin catalog, when requested, followed by the claims people judged."""
    learned = _learned_entries(target_file or get_common_hallucinations_file_path())
    return [*(_build_builtin_hallucinations() if include_builtin else []), *learned]


def save_common_hallucinations(
    entries: Sequence[CommonHallucinationEntry], target_file: Path | None = None
) -> None:
    """Replace the learned catalog with `entries`, under the ledger's lock."""
    update_learned(lambda _: list(entries), target_file)


def update_learned(
    change: Callable[[list[CommonHallucinationEntry]], list[CommonHallucinationEntry]],
    target_file: Path | None = None,
) -> list[CommonHallucinationEntry]:
    """Read the learned catalog, apply `change` and write what it returns, holding the lock.

    Verdicts and review threads read and write the ledger at once; without the lock, the
    last writer dropped every entry the others had added since it read.
    """
    fpath = target_file or get_common_hallucinations_file_path()
    with _ledger_lock(fpath):
        updated = change(_validated(_purged(fpath), fpath))
        _write_ledger([entry.model_dump(mode="json") for entry in updated], fpath)
    return updated


def register_common_hallucination(
    entry: CommonHallucinationEntry, target_file: Path | None = None
) -> CommonHallucinationEntry:
    """Record a claim a person judged, or count one more verdict on the claim already recorded.

    Only a person's judged claim is learned: anything else is refused.
    """
    if not _is_judged(entry.model_dump(mode="json")):
        raise InvalidEntryError(
            f"Only a claim a person judged is learned, not entry {entry.id[:64]!r}", field="entry"
        )
    registered = entry

    def merge(learned: list[CommonHallucinationEntry]) -> list[CommonHallucinationEntry]:
        nonlocal registered
        by_id = {e.id: e for e in learned}
        if (existing := by_id.get(entry.id)) is not None:
            registered = existing.model_copy(
                update={
                    "occurrence_count": existing.occurrence_count + 1,
                    "last_seen": datetime.now().isoformat(),
                    "resolution": entry.resolution or existing.resolution,
                }
            )
        by_id[entry.id] = registered
        return list(by_id.values())

    update_learned(merge, target_file)
    return registered


@contextmanager
def _ledger_lock(fpath: Path) -> Iterator[None]:
    """Hold the ledger's lock; closing the lock file releases it."""
    fpath.parent.mkdir(parents=True, exist_ok=True)
    lock_path = fpath.with_name(f"{fpath.name}{CONST_HALLUCINATIONS_LOCK_SUFFIX}")
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _is_judged(item: object) -> bool:
    """Whether a ledger record is a claim a person judged, the only kind the ledger keeps."""
    return (
        isinstance(item, dict)
        and item.get("source") == CONST_JUDGED_CLAIM_SOURCE
        and bool(item.get("judged"))
    )


def _learned_entries(fpath: Path) -> list[CommonHallucinationEntry]:
    """The judged claims in the ledger; any other entry is purged first, under the lock."""
    raw = _read_ledger(fpath)
    if not all(_is_judged(item) for item in raw):
        with _ledger_lock(fpath):
            raw = _purged(fpath)
    return _validated(raw, fpath)


def _purged(fpath: Path) -> list[Any]:
    """The ledger's judged claims, with every other entry removed from the file, once.

    The deterministic checks taught the ledger entries whose signatures pair common words; the
    first load after #950 removes them, and says so. Hold the lock while calling it.
    """
    raw = _read_ledger(fpath)
    kept = [item for item in raw if _is_judged(item)]
    if len(kept) < len(raw):
        _write_ledger(kept, fpath)
        logger.warning(
            "Removed %d entries the review's own checks had taught the learned catalog at %s. "
            "It now learns only from a person's INVALIDATED verdicts, each suppressing one claim "
            "about one piece of code.",
            len(raw) - len(kept),
            fpath,
        )
    return kept


def _read_ledger(fpath: Path) -> list[Any]:
    """The records a ledger file holds; a file that cannot be read warns and holds none."""
    if not fpath.is_file():
        return []
    try:
        raw = json.loads(fpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read the learned catalog at %s: %s", fpath, exc)
        return []
    if not isinstance(raw, list):
        logger.warning("The learned catalog at %s is not a JSON list", fpath)
        return []
    return raw


def _validated(raw: Iterable[Any], fpath: Path) -> list[CommonHallucinationEntry]:
    """The valid entries among `raw`; a malformed record is skipped alone, with a warning."""
    entries: list[CommonHallucinationEntry] = []
    for item in raw:
        try:
            entries.append(CommonHallucinationEntry.model_validate(item))
        except ValidationError as exc:
            logger.warning("Skipping a malformed learned-catalog record in %s: %s", fpath, exc)
    return entries


def _write_ledger(raw: Sequence[Any], fpath: Path) -> None:
    """Replace the ledger file with `raw` at once, so a reader never sees half of it."""
    temp_path = fpath.with_suffix(f".tmp-{uuid4().hex[:6]}")
    temp_path.write_text(json.dumps(list(raw), indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(fpath)


# ── Text & Pattern Signature Matching ────────────────────────────────────────


def _check_file_pattern_match(file_name: str, patterns: list[str]) -> bool:
    """Evaluate whether a file name matches any glob patterns in the entry."""
    if not patterns or "*" in patterns:
        return True
    from fnmatch import fnmatch

    return any(
        fnmatch(file_name, pat) or fnmatch(file_name.lower(), pat.lower()) for pat in patterns
    )


def _is_degenerate_signature(pattern: str) -> bool:
    """Detect a signature that is a bare prose word rather than a code identifier.

    Auto-learning once persisted single English words such as ``unvalidated``,
    ``traversal``, and ``unbounded`` as complete signatures. Those match nearly every
    genuine security finding, so a builtin entry carrying one is rejected at match time.

    A bare *code identifier* remains a valid signature: ``DEFAULT_HTTP_BROKER`` and
    ``FastMCP`` name one specific symbol, whereas an all-lowercase alphabetic word is
    prose and cannot distinguish a false alarm from a real defect.
    """
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]*", pattern):
        return False
    # Underscores, digits, hyphens, or internal capitals mark a code identifier.
    return pattern.islower() and pattern.isalpha()


def _check_signature_match(finding_text: str, signatures: list[str]) -> list[str]:
    """Evaluate if finding text matches any explicit signature regex, returning matched text."""
    matches: list[str] = []
    for pattern in signatures:
        if _is_degenerate_signature(pattern):
            logger.debug("Ignoring degenerate bare-word hallucination signature %r", pattern)
            continue
        try:
            m = re.search(pattern, finding_text, re.IGNORECASE)
            if m:
                matches.append(m.group(0) or pattern)
        except re.error:
            logger.debug("Skipping invalid hallucination signature regex %r", pattern)
    return matches


def _check_keyword_compound_match(finding_text: str, keywords: list[str]) -> list[str]:
    """Find matching non-common distinctive keywords in finding text."""
    clean_text = finding_text.lower()
    matches: list[str] = []
    for kw in keywords:
        clean_kw = kw.lower().strip()
        if clean_kw in _FORBIDDEN_COMMON_WORDS or len(clean_kw) <= 3:
            continue
        if clean_kw in clean_text:
            matches.append(kw)
    return matches


def _extract_defined_ast_names(tree: ast.AST) -> set[str]:
    """Extract all function, class, and assignment symbol names defined in an AST."""
    defined_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            defined_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)
    return defined_names


def _find_module_file_candidates(module_name: str, level: int, file_path: Path) -> list[Path]:
    """Resolve Python module name and import level to potential disk paths."""
    mod_parts = module_name.split(".")
    rel_path = Path(*mod_parts).with_suffix(".py")
    if level > 0:
        parent_dir = file_path.parent
        for _ in range(level - 1):
            parent_dir = parent_dir.parent
        return [parent_dir / rel_path, parent_dir / Path(*mod_parts) / "__init__.py"]

    repo_root = file_path.parent
    while repo_root.parent != repo_root:
        if (repo_root / "pyproject.toml").exists() or (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    return [
        repo_root / "src" / rel_path,
        repo_root / rel_path,
        file_path.parent / rel_path,
    ]


def _file_defines_symbol(path: Path, sym: str) -> bool:
    """Check whether a python file defines a given symbol in AST or text."""
    if not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(content)
        if sym in _extract_defined_ast_names(tree):
            return True
        return any(pattern in content for pattern in (f"def {sym}", f"class {sym}", f"{sym} ="))
    except Exception:
        return False


def _check_imported_module_for_symbol(tree: ast.AST, sym: str, file_path: Path) -> bool:
    """Check if sym is imported from another module in the repository that defines it."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        has_sym = any(alias.name == sym or alias.asname == sym for alias in node.names)
        if not has_sym:
            continue
        candidates = _find_module_file_candidates(node.module, node.level, file_path)
        if any(_file_defines_symbol(cand, sym) for cand in candidates):
            return True
    return False


def _verify_symbol_defined_in_ast_or_module(
    finding: Finding, tree: ast.AST, file_path: Path
) -> bool:
    """Verify whether a symbol claimed as missing actually exists in the file AST, imports, or exports."""
    finding_text = f"{finding.title} {finding.description or ''}"
    backtick_candidates = set(re.findall(r"`([A-Za-z0-9_]+)`", finding_text))
    clean_backticks = [s for s in backtick_candidates if s.lower() not in _FORBIDDEN_COMMON_WORDS]
    if clean_backticks:
        clean_symbols = clean_backticks
    else:
        word_candidates = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", finding_text))
        clean_symbols = [s for s in word_candidates if s.lower() not in _FORBIDDEN_COMMON_WORDS]

    if not clean_symbols:
        return False

    defined_names = _extract_defined_ast_names(tree)
    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    for sym in clean_symbols:
        if (
            sym in defined_names
            or f"{sym} =" in raw_text
            or f"def {sym}" in raw_text
            or f"class {sym}" in raw_text
            or _check_imported_module_for_symbol(tree, sym, file_path)
        ):
            return True

    return False


def _cited_lines(finding: Finding, file_path: Path, context: int = 1) -> str:
    """The lines a finding cites, with `context` lines either side; "" without a line."""
    numbers = [int(n) for n in re.findall(r"\d+", finding.location.partition(":")[2])]
    if not numbers:
        return ""
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[max(0, min(numbers) - 1 - context) : max(numbers) + context])


def _verify_syntax_grammar_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    if file_path.suffix.lower() != ".py":
        return False
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(content)
    except SyntaxError:
        return False
    del tree
    entry_id = entry.id.lower()
    if "json" in entry_id and "loads" in entry_id:
        return "json.loads" in content
    if "ast" in entry_id and "syntax" in entry_id:
        return "ast.parse" in content
    if "tenacity" in entry_id or "retry" in entry_id:
        return "create_retry_transport" in content or "is_retryable_status_code" in content
    if "async" in entry_id and "pool" in entry_id:
        return "aclose_shared_clients" in content or "_ASYNC_CLIENTS" in content
    if any(word in entry_id for word in ("missing", "symbol", "header")):
        return False
    return bool(SYNTAX_CLAIM.search(f"{finding.title}\n{finding.description or ''}"))


def _verify_secret_scanning_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    finding_text = f"{finding.title} {finding.description or ''}"
    has_masked_token = bool(
        re.search(r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}", finding_text, re.IGNORECASE)
    )
    if not has_masked_token:
        return False
    content = file_path.read_text(encoding="utf-8", errors="replace")
    if bool(re.search(r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}", content, re.IGNORECASE)):
        return True
    loc = finding.location
    if ":" in loc:
        try:
            line_str = loc.split(":", 1)[1]
            num = int(re.split(r"[\s\-]", line_str.strip())[0])
            lines = content.splitlines()
            if 1 <= num <= len(lines):
                target_line = lines[num - 1]
                has_masked = bool(
                    re.search(
                        r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}",
                        target_line,
                        re.IGNORECASE,
                    )
                )
                if has_masked:
                    return True
                # Clean line of getattr/get attribute keys and standard option name strings
                cleaned_line = re.sub(
                    r"(?:getattr|hasattr|setattr|\.get)\s*\([^)]*['\"][a-zA-Z0-9_]+['\"]",
                    "",
                    target_line,
                )
                cleaned_line = re.sub(
                    r"['\"](?:password|secret|token|api_key|host|port|db|key|name)['\"]",
                    "",
                    cleaned_line,
                )
                return not bool(re.search(r"['\"][^'\"]{6,}['\"]", cleaned_line))
        except Exception:
            pass
    return True


def _verify_dependency_ecosystem_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    entry_id = entry.id.upper()
    if any(kw in entry_id for kw in ("HTTPX2", "PATHLIB", "TIMEOUT")):
        return True
    try:
        from devops_cli.core.repo import find_repo_root

        root = find_repo_root(file_path)
        pyproj = root / "pyproject.toml"
        if pyproj.is_file():
            text = pyproj.read_text(encoding="utf-8", errors="replace").lower()
            finding_text = f"{finding.title} {finding.description or ''}".lower()
            return any(
                pkg in finding_text and pkg in text
                for pkg in ("httpx2", "pydantic", "pytest", "ruff", "mypy", "click", "typer")
            )
    except Exception:
        pass
    return False


def _verify_test_mocks_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    parts = set(file_path.parts)
    is_test = bool(
        parts & {"tests", "test", "fixtures", "golden"}
        or file_path.name.startswith(("test_", "mock_"))
        or file_path.name.endswith(("_test.py", ".example", ".sample"))
    )
    if not is_test:
        return False
    finding_text = f"{finding.title} {finding.description or ''}".lower()
    mock_keywords = (
        "sk-gateway",
        "sk-wrong",
        "dummy",
        "mock",
        "fake",
        "example.com",
        "test",
        "placeholder",
        "00000000",
        "assertion",
        "tuple",
        "traversal",
        "fixture",
    )
    return any(kw in finding_text for kw in mock_keywords)


def _verify_documentation_context_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    if file_path.name in ("common_hallucinations.json", "mitigated_findings.json"):
        return True
    parts = set(file_path.parts)
    if parts & {"docs", "tasks"} or file_path.suffix.lower() in (".md", ".rst", ".txt"):
        return True
    entry_id = entry.id.upper()
    if "k8s" in parts:
        return any(kw in entry_id for kw in ("OVERLAY", "NODEPORT", "HTTP", "PROMPT", "DOC"))
    if "JAEGER" in entry_id:
        try:
            return "jaegertracing/jaeger" in file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
    if "MITIGATION" in entry_id and "mitigated_findings" in file_path.name:
        try:
            return file_path.read_text(encoding="utf-8").strip() in ("[]", "")
        except OSError:
            return False
    if "PRICING" in entry_id and file_path.name == "pricing.py":
        return True
    return False


def _verify_mutable_defaults_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    return "default_factory" in _cited_lines(finding, file_path)


def _is_unbounded_stream_op(target_line: str) -> bool:
    stream_kws = ("request", "body", "stream", "websocket", "recv", "socket", "iter_bytes")
    return any(kw in target_line for kw in stream_kws)


def _check_boundary_cwe400_local_file(finding: Finding, file_path: Path) -> bool:
    loc = finding.location
    if ":" in loc:
        try:
            line_str = loc.split(":", 1)[1]
            num = int(re.split(r"[\s\-]", line_str.strip())[0])
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if 1 <= num <= len(lines):
                target_line = lines[num - 1].lower()
                is_local = any(
                    op in target_line for op in (".read_text(", "read_text()", "open(", "path(")
                )
                return is_local and not _is_unbounded_stream_op(target_line)
        except Exception:
            pass
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace").lower()
        is_local_read = ".read_text(" in content or "open(" in content
        is_stream = any(kw in content for kw in ("websocket", "request.body", "iter_bytes"))
        return is_local_read and not is_stream
    except Exception:
        return False


def _verify_boundary_errors_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    finding_text = f"{finding.title} {finding.description or ''}".lower()
    if _UNTRUSTED_INPUT_CLAIM.search(finding_text):
        return False
    entry_id = entry.id.upper()
    if "GPU-FEATURE-DISCOVERY" in entry_id:
        return "gpu-feature-discovery" in str(file_path).lower()
    if "KUBE-ROUTER" in entry_id:
        return "networkpolicy" in str(file_path).lower()
    if any(pat in finding_text for pat in ("cwe-400", "cwe400", "read_text", "exhaustion")):
        return _check_boundary_cwe400_local_file(finding, file_path)
    return False


def _verify_general_ground_truth(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path
) -> bool:
    entry_id = entry.id.upper()
    finding_text = f"{finding.title} {finding.description or ''}".lower()
    if "ERROR-METRICS" in entry_id:
        try:
            return "type(exc).__name__" in file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
    if "PROMETHEUS" in entry_id or "TELEMETRY" in entry_id:
        return any(
            term in finding_text for term in ("promql", "prometheus", "opentelemetry", "query")
        )
    if "LOCALHOST" in entry_id or "LOOPBACK" in entry_id:
        return any(term in finding_text for term in ("localhost", "127.0.0.1", "loopback"))
    return False


_GROUND_TRUTH_VERIFIERS: dict[
    HallucinationCategory,
    Callable[[Finding, CommonHallucinationEntry, Path], bool],
] = {
    HallucinationCategory.SYNTAX_GRAMMAR: _verify_syntax_grammar_ground_truth,
    HallucinationCategory.SECRET_SCANNING: _verify_secret_scanning_ground_truth,
    HallucinationCategory.DEPENDENCY_ECOSYSTEM: _verify_dependency_ecosystem_ground_truth,
    HallucinationCategory.TEST_MOCKS: _verify_test_mocks_ground_truth,
    HallucinationCategory.DOCUMENTATION_CONTEXT: _verify_documentation_context_ground_truth,
    HallucinationCategory.MUTABLE_DEFAULTS: _verify_mutable_defaults_ground_truth,
    HallucinationCategory.BOUNDARY_ERRORS: _verify_boundary_errors_ground_truth,
    HallucinationCategory.GENERAL: _verify_general_ground_truth,
}


def verify_ground_truth_hallucination(
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path | None
) -> bool:
    """Verify ground truth in the actual target file before allowing hallucination invalidation.

    Guarantees that real defects, syntax errors, or plaintext secrets are NEVER invalidated.
    """
    if file_path is None or not file_path.exists() or not file_path.is_file():
        return False
    verifier = _GROUND_TRUTH_VERIFIERS.get(entry.category)
    return verifier(finding, entry, file_path) if verifier else False


def calculate_hallucination_similarity(  # noqa: C901
    finding: Finding, entry: CommonHallucinationEntry, file_path: Path | None = None
) -> HallucinationMatch:
    """Calculate similarity between a finding and a known common hallucination.

    ENFORCES SAFETY:
    1. Generic words (secret, token, error, etc.) are strictly excluded.
    2. Explicit signature regex matching is required.
    3. If target file is present for syntax claims, real syntax errors yield 0.0 score.
    """
    finding_text = f"{finding.title} {finding.description or ''}"
    loc_file = finding.location.split(":")[0].strip()
    file_matched = _check_file_pattern_match(
        Path(loc_file).name, entry.file_patterns
    ) or _check_file_pattern_match(loc_file, entry.file_patterns)

    # Check explicit signature patterns first
    sig_matches = _check_signature_match(finding_text, entry.signature_patterns)
    matched_kws = _check_keyword_compound_match(finding_text, entry.pattern_keywords)

    if not (sig_matches or matched_kws):
        return HallucinationMatch(
            hallucination=entry,
            similarity_score=0.0,
            matched_keywords=[],
            reason="No signature pattern or distinctive compound keyword match",
        )

    finding_text_lower = finding_text.lower()

    # Category-specific domain validation guards
    if entry.category == HallucinationCategory.SYNTAX_GRAMMAR:
        syntax_indicators = (
            "syntax",
            "grammar",
            "except",
            "exception clause",
            "bracketless",
            "parentheses",
            "unparenthesized",
            "pep758",
            "python 2",
            "nameerror",
            "importerror",
            "undefined",
            "uninitialized",
            "unboundlocalerror",
            "placeholder",
            "symbol",
            "import",
            "missing",
            "identifier",
        )
        if not any(si in finding_text_lower for si in syntax_indicators):
            return HallucinationMatch(
                hallucination=entry,
                similarity_score=0.0,
                matched_keywords=[],
                reason="Finding does not describe a syntax or grammar issue",
            )

        if file_path and file_path.exists() and file_path.suffix.lower() == ".py":
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                # Real syntax error in source! Never match as hallucination.
                return HallucinationMatch(
                    hallucination=entry,
                    similarity_score=0.0,
                    matched_keywords=[],
                    reason="Target file has genuine SyntaxError; real defect confirmed",
                )

    if entry.category == HallucinationCategory.SECRET_SCANNING:
        secret_indicators = (
            "secret",
            "token",
            "key",
            "password",
            "credential",
            "masked",
            "redacted",
        )
        if not any(si in finding_text_lower for si in secret_indicators):
            return HallucinationMatch(
                hallucination=entry,
                similarity_score=0.0,
                matched_keywords=[],
                reason="Finding does not describe a secret, token, or credential issue",
            )

        # If it's a secret finding, it MUST match a masked placeholder pattern specifically
        has_masked_sig = bool(
            re.search(
                r"<masked-[a-zA-Z0-9_\-]+>|\*{3,}redacted\*{3,}|<secret-placeholder>",
                finding_text,
                re.IGNORECASE,
            )
        )
        if not has_masked_sig:
            return HallucinationMatch(
                hallucination=entry,
                similarity_score=0.0,
                matched_keywords=[],
                reason="Finding does not reference a verified masked/redacted placeholder",
            )

    # Require minimum 2 compound keywords if no explicit regex signature matched
    if not sig_matches and len(matched_kws) < 2:
        return HallucinationMatch(
            hallucination=entry,
            similarity_score=0.0,
            matched_keywords=matched_kws,
            reason="Insufficient compound keywords matched without signature pattern",
        )

    all_matched = list(dict.fromkeys(sig_matches + matched_kws))
    total_expected = max(1, len(entry.pattern_keywords))
    keyword_overlap = len(matched_kws) / total_expected

    if sig_matches:
        # Regex signature match represents structural pattern match (>= 0.70 confidence)
        # Scaled by keyword overlap for bonus confidence up to 1.0
        score = round(min(1.0, 0.70 + 0.30 * keyword_overlap), 3)
    else:
        # Without regex signature, score reflects normalized keyword overlap capped at 0.65
        score = round(min(0.65, keyword_overlap), 3)

    if not file_matched:
        score = round(score * 0.5, 3)

    return HallucinationMatch(
        hallucination=entry,
        similarity_score=score,
        matched_keywords=all_matched,
        reason=f"Matched signature/keywords for [{entry.id}]",
    )


def find_similar_hallucinations(
    finding: Finding,
    threshold: float = 0.5,
    file_path: Path | None = None,
) -> list[HallucinationMatch]:
    """Find the builtin entries matching the candidate finding.

    A claim a person judged is matched exactly, by `find_judged_entry`, never by signature.
    """
    matches: list[HallucinationMatch] = []

    for entry in _build_builtin_hallucinations():
        m = calculate_hallucination_similarity(finding, entry, file_path=file_path)
        if m.similarity_score >= threshold:
            matches.append(m)

    matches.sort(key=lambda x: x.similarity_score, reverse=True)
    return matches


def is_common_hallucination(
    finding: Finding,
    threshold: float = 0.6,
    file_path: Path | None = None,
) -> HallucinationMatch | None:
    """Return top hallucination match if finding exceeds similarity threshold, else None."""
    matches = find_similar_hallucinations(finding, threshold=threshold, file_path=file_path)
    return matches[0] if matches else None


# ── The Claims People Judged ─────────────────────────────────────────────────


def record_judged_claim(finding: SavedFinding, reason: str) -> CommonHallucinationEntry | None:
    """Record the claim a person's INVALIDATED verdict on `finding` suppresses from now on.

    The claim is keyed on the code the review recorded the finding citing. None when the review
    recorded none, as a session saved before #950 did, or the finding names no code name of that
    code: nothing is recorded then. The file as it reads now may hold code the person never saw.
    """
    claim = judged_claim(finding, finding.cited_code) if finding.cited_code else None
    if claim is None:
        return None
    key_digest = hashlib.sha256(claim.model_dump_json().encode()).hexdigest()[:12].upper()
    return register_common_hallucination(
        CommonHallucinationEntry(
            id=f"{CONST_JUDGED_CLAIM_ID_PREFIX}{key_digest}",
            name=finding.title,
            category=HallucinationCategory.GENERAL,
            description=finding.description or finding.title,
            resolution=reason,
            source=CONST_JUDGED_CLAIM_SOURCE,
            judged=claim,
        )
    )


def find_judged_entry(
    finding: Finding, file_path: Path, root: Path | None
) -> CommonHallucinationEntry | None:
    """The learned entry recording a person's verdict on the claim `finding` makes, if any.

    `file_path` is the file the finding cites, in the checkout `root` belongs to (the working
    directory's without one). It matches on that checkout's project, the file, the line the
    location cites, the code there and the code names the finding gives, whichever tool or
    persona raised either finding.
    """
    learned = load_common_hallucinations(include_builtin=False)
    if not learned:
        return None
    cited = cited_code(finding.location, file_path, find_worktree_root(root or Path.cwd()))
    claim = judged_claim(finding, cited) if cited else None
    if claim is None:
        return None
    return next((e for e in learned if e.judged == claim), None)


def _infer_hallucination_category(title: str, reason: str) -> HallucinationCategory:
    """Map distinctive non-common terms in title and reason to HallucinationCategory."""
    combined = f"{title} {reason}".lower()
    dispatch_rules: list[tuple[set[str], HallucinationCategory]] = [
        (
            {"pep758", "bracketless", "unparenthesized", "grammar"},
            HallucinationCategory.SYNTAX_GRAMMAR,
        ),
        ({"masked", "redacted", "sanitization_marker"}, HallucinationCategory.SECRET_SCANNING),
        (
            {"dummy_token", "rfc2606", "example.com", "fake_credential"},
            HallucinationCategory.TEST_MOCKS,
        ),
        ({"typosquat", "httpx2"}, HallucinationCategory.DEPENDENCY_ECOSYSTEM),
        ({"anti-pattern", "educational"}, HallucinationCategory.DOCUMENTATION_CONTEXT),
        ({"default_factory", "pydantic_field"}, HallucinationCategory.MUTABLE_DEFAULTS),
        (
            {
                "eof",
                "out_of_bounds",
                "cwe_400",
                "cwe-400",
                "cwe400",
                "read_text",
                "uncontrolled_resource_consumption",
            },
            HallucinationCategory.BOUNDARY_ERRORS,
        ),
    ]
    for keywords, category in dispatch_rules:
        if any(kw in combined for kw in keywords):
            return category
    return HallucinationCategory.GENERAL


def remove_learned_hallucinations(
    ids: Iterable[str] | None = None, target_file: Path | None = None
) -> list[str]:
    """Remove learned entries by id, or all of them when no ids are given; return the removed."""
    removed: list[str] = []

    def remove(learned: list[CommonHallucinationEntry]) -> list[CommonHallucinationEntry]:
        wanted = set(ids) if ids is not None else {e.id for e in learned}
        removed.extend(e.id for e in learned if e.id in wanted)
        return [e for e in learned if e.id not in wanted]

    update_learned(remove, target_file)
    return removed


def render_negative_exemplars(
    target: Path,
    limit: int = DEFAULT_HALLUCINATION_EXEMPLAR_COUNT,
    max_chars: int = DEFAULT_HALLUCINATION_EXEMPLAR_CHARS,
) -> str:
    """Render the false positives a persona is told not to raise again, as a prompt block.

    These are the claims people disproved in reviews of the target, the repository `target`
    belongs to, the most often judged first: recurrence a person confirmed is what a reviewer
    should stop repeating. Until a person has judged one there, the curated builtin entries are
    shown instead, under a heading that does not claim they were reported against this codebase.
    Another repository's judged claims are never shown: they describe code this review cannot see.

    Showing a persona what has been disproved costs a few hundred tokens once per segment;
    re-deriving those findings costs a generation and a verification each. Only the head of the
    distribution is shown, because recurrence is concentrated there.
    """
    project = project_of(target)
    judged = sorted(
        (
            e
            for e in load_common_hallucinations(include_builtin=False)
            if e.judged is not None and e.judged.project == project
        ),
        key=lambda e: (e.occurrence_count, e.last_seen),
        reverse=True,
    )
    if judged:
        lines = [_judged_exemplar(e) for e in judged[: max(0, limit)]]
        return _exemplar_block("negative_exemplars_judged.md", lines, max_chars)
    shipped = [e.description or e.name for e in _build_builtin_hallucinations()]
    return _exemplar_block("negative_exemplars_shipped.md", shipped[: max(0, limit)], max_chars)


def _judged_exemplar(entry: CommonHallucinationEntry) -> str:
    """A judged claim as a persona is shown it: the title, the file, and why it is wrong."""
    where = f" ({entry.judged.file})" if entry.judged else ""
    why = f": {entry.resolution}" if entry.resolution else ""
    return f"{entry.name}{where}{why}"


def _exemplar_block(heading_prompt: str, lines: Sequence[str], max_chars: int) -> str:
    """`lines` under the heading prompt names, each cut to `max_chars`; "" with no lines.

    A judged claim's title and reason came from a model, a scanner and a person, so they are
    masked and their prompt boundary tags escaped, as a target's conventions are.
    """
    shown = [
        f"- {sanitize_prompt_boundary_tags(mask_secrets(line.strip()))[:max_chars]}"
        for line in lines
        if line.strip()
    ]
    if not shown:
        return ""
    return f"\n\n{load_task_prompt(heading_prompt)}\n" + "\n".join(shown)
