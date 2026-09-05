"""Unit tests for the Common AI Hallucinations catalog and management system."""

from pathlib import Path

import pytest

from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    auto_record_invalidated_finding,
    calculate_hallucination_similarity,
    find_similar_hallucinations,
    get_common_hallucinations_file_path,
    is_common_hallucination,
    load_common_hallucinations,
    register_common_hallucination,
    save_common_hallucinations,
)
from devops_cli.ai.review_schema import Finding


def test_builtin_catalog_contains_pep758_and_essential_entries() -> None:
    """Verify built-in catalog contains PEP 758 and essential false-positive definitions."""
    entries = load_common_hallucinations(include_builtin=True)
    ids = {e.id for e in entries}

    assert "HALLUCINATION-PEP758-EXCEPT" in ids
    assert "HALLUCINATION-MASKED-SECRET" in ids
    assert "HALLUCINATION-TEST-MOCK-CRED" in ids
    assert "HALLUCINATION-HTTPX2-DEPENDENCY" in ids
    assert "HALLUCINATION-PYDANTIC-MUTABLE-DEFAULT" in ids
    assert "HALLUCINATION-DOC-ANTI-PATTERN" in ids

    pep758 = next(e for e in entries if e.id == "HALLUCINATION-PEP758-EXCEPT")
    assert pep758.category == HallucinationCategory.SYNTAX_GRAMMAR
    assert "PEP 758" in pep758.resolution
    assert any("except" in kw for kw in pep758.pattern_keywords)


def test_save_and_load_common_hallucinations(tmp_path: Path) -> None:
    """Verify saving and loading custom hallucinations to a designated file path."""
    data_file = tmp_path / "custom_hallucinations.json"

    custom_entry = CommonHallucinationEntry(
        id="HALLUCINATION-CUSTOM-TEST",
        name="Custom Test Hallucination",
        category=HallucinationCategory.GENERAL,
        description="A test hallucination description",
        pattern_keywords=["custom", "hallucination", "test"],
        resolution="Resolved via custom test rule",
        occurrence_count=3,
        source="custom",
    )

    save_common_hallucinations([custom_entry], target_file=data_file)
    assert data_file.exists()

    loaded = load_common_hallucinations(target_file=data_file, include_builtin=False)
    assert len(loaded) == 1
    assert loaded[0].id == "HALLUCINATION-CUSTOM-TEST"
    assert loaded[0].occurrence_count == 3


def test_get_common_hallucinations_file_path_respects_env_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify get_common_hallucinations_file_path respects DEVOPS_CLI_DATA_DIR."""
    agent_dir = tmp_path / ".data" / "agent"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(agent_dir))

    path = get_common_hallucinations_file_path()
    assert str(path).startswith(str(agent_dir))
    assert path.name == "common_hallucinations.json"


def test_calculate_similarity_pep758_syntax_claim(tmp_path: Path) -> None:
    """Verify calculating similarity for a finding claiming bracketless except is a syntax error."""
    py_file = tmp_path / "handler.py"
    py_file.write_text(
        "try:\n    connect()\nexcept TimeoutError, ConnectionRefusedError:\n    pass\n",
        encoding="utf-8",
    )

    finding = Finding(
        title="Syntax error: invalid unparenthesized except clause",
        description="Python requires parentheses for multiple exception types in except statement.",
        location=f"{py_file.name}:3",
        severity="HIGH",
        status="UNVERIFIED",
    )

    entries = load_common_hallucinations(include_builtin=True)
    pep758_entry = next(e for e in entries if e.id == "HALLUCINATION-PEP758-EXCEPT")

    match = calculate_hallucination_similarity(finding, pep758_entry, file_path=py_file)
    assert match.similarity_score >= 0.7
    assert any("except" in m.lower() for m in match.matched_keywords)
    assert match.hallucination.id == "HALLUCINATION-PEP758-EXCEPT"


def test_find_similar_hallucinations_and_is_common_hallucination(tmp_path: Path) -> None:
    """Verify finding similar hallucinations and checking if finding matches threshold."""
    finding = Finding(
        title="Hardcoded API Secret in code: <masked-api-key>",
        description="The file contains a plaintext credential placeholder '<masked-api-key>' that should be removed.",
        location="config.py:12",
        severity="CRITICAL",
        status="UNVERIFIED",
    )

    matches = find_similar_hallucinations(finding, threshold=0.4)
    assert len(matches) > 0
    top_match = matches[0]
    assert top_match.hallucination.id == "HALLUCINATION-MASKED-SECRET"
    assert top_match.similarity_score >= 0.5

    match_direct = is_common_hallucination(finding, threshold=0.4)
    assert match_direct is not None
    assert match_direct.hallucination.id == "HALLUCINATION-MASKED-SECRET"


def test_register_common_hallucination_updates_existing(tmp_path: Path) -> None:
    """Registering an existing hallucination updates occurrence count and timestamp."""
    data_file = tmp_path / "hallucinations.json"

    entry = CommonHallucinationEntry(
        id="HALLUCINATION-CUSTOM-1",
        name="Custom 1",
        category=HallucinationCategory.GENERAL,
        description="Custom description",
        pattern_keywords=["sample", "keyword"],
        resolution="Sample resolution",
        occurrence_count=1,
    )
    register_common_hallucination(entry, target_file=data_file)

    # Register again with new keyword
    entry_updated = entry.model_copy(
        update={"occurrence_count": 5, "pattern_keywords": ["sample", "keyword", "extra"]}
    )
    register_common_hallucination(entry_updated, target_file=data_file)

    loaded = load_common_hallucinations(target_file=data_file, include_builtin=False)
    assert len(loaded) == 1
    assert loaded[0].occurrence_count == 5
    assert "extra" in loaded[0].pattern_keywords


def test_auto_record_invalidated_finding_updates_existing(tmp_path: Path) -> None:
    """Auto-recording an invalidated finding that matches an existing pattern increments count."""
    data_file = tmp_path / "hallucinations.json"

    finding = Finding(
        title="Syntax error in except clause without parentheses",
        description="Found except ErrorA, ErrorB: which is invalid syntax.",
        location="test.py:10",
        severity="HIGH",
        status="INVALIDATED",
        invalidation_reason="Valid Python 3.14 PEP 758 syntax",
    )

    recorded = auto_record_invalidated_finding(
        finding, target_file=data_file, reason="Valid Python 3.14 PEP 758 syntax"
    )
    assert recorded is not None
    assert recorded.id == "HALLUCINATION-PEP758-EXCEPT"
    assert recorded.occurrence_count >= 2

    # Verify persisted in file
    loaded = load_common_hallucinations(target_file=data_file, include_builtin=False)
    assert any(e.id == "HALLUCINATION-PEP758-EXCEPT" for e in loaded)


def test_auto_record_invalidated_finding_creates_new_entry(tmp_path: Path) -> None:
    """Auto-recording an uncatalogued invalidated finding creates a new auto-learned entry."""
    data_file = tmp_path / "hallucinations.json"

    finding = Finding(
        title="Quirky Framework Obsolete Artifact Warning",
        description="Flagged obsolete widget architecture in template engine.",
        location="templates/view.html:4",
        severity="LOW",
        status="INVALIDATED",
        invalidation_reason="Template engine legitimately supports widget syntax in v3",
    )

    recorded = auto_record_invalidated_finding(
        finding,
        target_file=data_file,
        reason="Template engine legitimately supports widget syntax in v3",
    )
    assert recorded is not None
    assert recorded.source == "auto_learned"
    assert "widget" in recorded.pattern_keywords or "quirky" in recorded.pattern_keywords
    assert recorded.occurrence_count == 1

    loaded = load_common_hallucinations(target_file=data_file, include_builtin=False)
    assert any(e.id == recorded.id for e in loaded)


def test_deterministic_pre_verification_integrates_common_hallucinations(tmp_path: Path) -> None:
    """Deterministic pre-verification immediately invalidates high-confidence common hallucinations."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    py_file = tmp_path / "modern_service.py"
    py_file.write_text(
        "try:\n    fetch_data()\nexcept TimeoutError, ConnectionRefusedError:\n    pass\n",
        encoding="utf-8",
    )

    finding = Finding(
        title="Syntax error: bracketless except clause without parentheses",
        description="Found except TimeoutError, ConnectionRefusedError: which is invalid Python syntax.",
        location=f"{py_file.name}:3",
        severity="HIGH",
        status="UNVERIFIED",
    )

    result = _deterministic_pre_verification(finding, repo_root=tmp_path)
    assert result.status == "INVALIDATED"
    assert result.verified is False
    assert result.reportable is False
    assert (
        "PEP 758" in (result.invalidation_reason or "")
        or "HALLUCINATION-PEP758-EXCEPT" in (result.invalidation_reason or "")
        or "Syntax validation passed" in (result.invalidation_reason or "")
    )


def test_real_security_finding_never_flagged_or_invalidated(tmp_path: Path) -> None:
    """Real security findings with sensitive keywords must NEVER be flagged as hallucinations."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    auth_file = tmp_path / "auth.py"
    auth_file.write_text('API_KEY = "AKIA1234567890ABCDEF"\n', encoding="utf-8")

    real_finding = Finding(
        title="Hardcoded API Secret in code: Exposed Token",
        description="The file contains a plaintext API key 'AKIA1234567890ABCDEF' in auth.py.",
        location=f"{auth_file.name}:1",
        severity="CRITICAL",
        status="UNVERIFIED",
    )

    match = is_common_hallucination(real_finding, threshold=0.5, file_path=auth_file)
    assert match is None

    result = _deterministic_pre_verification(real_finding, repo_root=tmp_path)
    assert result.status == "UNVERIFIED"
    assert result.verified is False
    assert result.invalidation_reason is None


def test_real_syntax_error_never_flagged_or_invalidated(tmp_path: Path) -> None:
    """Real syntax errors in code must NEVER be flagged as PEP 758 hallucinations."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    bad_syntax_file = tmp_path / "broken.py"
    bad_syntax_file.write_text(
        "try:\n    connect()\nexcept (ValueError TypeError):\n    pass\n", encoding="utf-8"
    )

    real_syntax_finding = Finding(
        title="Syntax error: invalid syntax in except clause",
        description="Missing comma between exceptions in except statement.",
        location=f"{bad_syntax_file.name}:3",
        severity="HIGH",
        status="UNVERIFIED",
    )

    match = is_common_hallucination(real_syntax_finding, threshold=0.5, file_path=bad_syntax_file)
    assert match is None

    result = _deterministic_pre_verification(real_syntax_finding, repo_root=tmp_path)
    assert result.status == "UNVERIFIED"
    assert result.invalidation_reason is None


def test_real_mutable_default_argument_never_flagged_or_invalidated(tmp_path: Path) -> None:
    """Standard Python mutable default argument findings must NEVER be flagged as Pydantic hallucinations."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    func_file = tmp_path / "processor.py"
    func_file.write_text("def process(items=[]):\n    items.append(1)\n", encoding="utf-8")

    real_mutable_finding = Finding(
        title="Mutable default argument in function process",
        description="Function process uses default list [] which retains state across invocations.",
        location=f"{func_file.name}:1",
        severity="MEDIUM",
        status="UNVERIFIED",
    )

    match = is_common_hallucination(real_mutable_finding, threshold=0.5, file_path=func_file)
    assert match is None

    result = _deterministic_pre_verification(real_mutable_finding, repo_root=tmp_path)
    assert result.status == "UNVERIFIED"
    assert result.invalidation_reason is None


def test_forbidden_common_words_excluded_from_similarity_matching() -> None:
    """Generic common English words cannot contribute to hallucination matching."""
    from devops_cli.ai.review.common_hallucinations import _FORBIDDEN_COMMON_WORDS

    assert "secret" in _FORBIDDEN_COMMON_WORDS
    assert "token" in _FORBIDDEN_COMMON_WORDS
    assert "test" in _FORBIDDEN_COMMON_WORDS
    assert "error" in _FORBIDDEN_COMMON_WORDS
    assert "syntax" in _FORBIDDEN_COMMON_WORDS

    # Finding containing only forbidden words
    finding = Finding(
        title="Secret token error in test file",
        description="Found security vulnerability with code line syntax error.",
        location="test.py:5",
        severity="HIGH",
        status="UNVERIFIED",
    )

    matches = find_similar_hallucinations(finding, threshold=0.3)
    assert len(matches) == 0
