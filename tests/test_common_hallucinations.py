"""Unit tests for the Common AI Hallucinations catalog and management system."""

from pathlib import Path

import pytest

from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    _build_builtin_hallucinations,
    calculate_hallucination_similarity,
    find_similar_hallucinations,
    get_common_hallucinations_file_path,
    is_common_hallucination,
    load_common_hallucinations,
    record_judged_claim,
    register_common_hallucination,
    save_common_hallucinations,
)
from devops_cli.ai.review.judged_claims import JudgedClaim
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.exceptions.validation import ValidationError


def _judged(file: str = "a.py", project: str = "target") -> JudgedClaim:
    """A claim a person judged about one line of `file`."""
    return JudgedClaim(project=project, file=file, line=1, code_sha256="0" * 64, claim=("exec",))


def test_builtin_catalog_contains_pep758_and_essential_entries() -> None:
    """Verify built-in catalog contains PEP 758 and essential false-positive definitions."""
    entries = load_common_hallucinations(include_builtin=True)
    ids = {e.id for e in entries}

    expected_ids = {
        "HALLUCINATION-PEP758-EXCEPT",
        "HALLUCINATION-MASKED-SECRET",
        "HALLUCINATION-TEST-MOCK-CRED",
        "HALLUCINATION-HTTPX2-DEPENDENCY",
        "HALLUCINATION-PYDANTIC-MUTABLE-DEFAULT",
        "HALLUCINATION-DOC-ANTI-PATTERN",
        "HALLUCINATION-GRAPHQL-JSON-DUMPS",
        "HALLUCINATION-EXAMPLE-COM-WEBHOOK",
        "HALLUCINATION-PROMETHEUS-TELEMETRY-METRIC",
    }
    assert (expected_ids.issubset(ids),) == (True,)

    pep758 = next(e for e in entries if e.id == "HALLUCINATION-PEP758-EXCEPT")
    assert (
        pep758.category,
        "PEP 758" in pep758.resolution,
        any("except" in kw for kw in pep758.pattern_keywords),
    ) == (HallucinationCategory.SYNTAX_GRAMMAR, True, True)


def test_save_and_load_common_hallucinations(tmp_path: Path) -> None:
    """Verify saving and loading custom hallucinations to a designated file path."""
    data_file = tmp_path / "custom_hallucinations.json"

    custom_entry = CommonHallucinationEntry(
        id="HALLUCINATION-CUSTOM-TEST",
        name="Custom Test Hallucination",
        category=HallucinationCategory.GENERAL,
        description="A test hallucination description",
        resolution="Resolved via custom test rule",
        occurrence_count=3,
        source="person",
        judged=_judged(),
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
    """Registering a judged claim again counts one more verdict and keeps the latest reason."""
    data_file = tmp_path / "hallucinations.json"

    entry = CommonHallucinationEntry(
        id="JUDGED-CUSTOM-1",
        name="Custom 1",
        category=HallucinationCategory.GENERAL,
        description="Custom description",
        resolution="Sample resolution",
        source="person",
        judged=_judged(),
    )
    register_common_hallucination(entry, target_file=data_file)
    register_common_hallucination(
        entry.model_copy(update={"resolution": "Second reason"}), target_file=data_file
    )

    loaded = load_common_hallucinations(target_file=data_file, include_builtin=False)
    assert [(e.id, e.occurrence_count, e.resolution) for e in loaded] == [
        ("JUDGED-CUSTOM-1", 2, "Second reason")
    ]


def test_a_builtin_entry_is_never_learned(tmp_path: Path) -> None:
    """A builtin entry is never widened or persisted by learning (#514), and nothing but a
    claim a person judged is learned (#950).

    Learning used to add the finding's words to the builtin entry and persist the copy, which
    then shadowed the shipped entry and matched ever more real findings.
    """
    data_file = tmp_path / "hallucinations.json"
    builtin = next(
        e for e in _build_builtin_hallucinations() if e.id == "HALLUCINATION-PEP758-EXCEPT"
    )

    with pytest.raises(ValidationError):
        register_common_hallucination(builtin, target_file=data_file)

    assert load_common_hallucinations(target_file=data_file, include_builtin=False) == []


def test_a_persons_verdict_records_the_claim_it_disproved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A person's INVALIDATED verdict records the project, the file, the line and code the review
    recorded the finding citing, and the identifiers of that code the title names, under the
    person's reason."""
    from devops_cli.ai.review.verification import record_cited_code

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'site'\n", encoding="utf-8")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "view.html").write_text(
        "<html>\n<body>\n<main>\n  {{ widget.render(artifact) }}\n</main>\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    finding = SavedFinding(
        title="Quirky Framework Obsolete Artifact Warning",
        description="Flagged obsolete widget architecture in template engine.",
        location="templates/view.html:4",
        severity="LOW",
    )
    record_cited_code([finding], tmp_path)

    recorded = record_judged_claim(finding, "The engine supports widget syntax in v3")

    assert recorded is not None
    assert (
        recorded.source,
        recorded.resolution,
        recorded.judged and (recorded.judged.project, recorded.judged.file, recorded.judged.line),
        recorded.judged and recorded.judged.claim,
        [e.id for e in load_common_hallucinations(include_builtin=False)],
    ) == (
        "person",
        "The engine supports widget syntax in v3",
        (tmp_path.name, "templates/view.html", 4),
        ("artifact",),
        [recorded.id],
    )


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


def test_cataloged_hallucinations_matching() -> None:
    """Verify cataloged hallucinations match correctly."""
    entries = load_common_hallucinations(include_builtin=True)
    entry_ids = {e.id for e in entries}

    assert "HALLUCINATION-UNINITIALIZED-VARIABLE-ABOVE-LOOP" in entry_ids
    assert "HALLUCINATION-PATHLIB-RESOLVE-FILENOTFOUND" in entry_ids
    assert "HALLUCINATION-HEALTH-ENDPOINT-VERSION" in entry_ids
    assert "HALLUCINATION-STREAM-EVENT-TIMESTAMP" in entry_ids
    assert "HALLUCINATION-NONEXISTENT-FIXER-PAYLOAD" in entry_ids
    assert "HALLUCINATION-CI-ALLOW-BLOCKED-STATE" in entry_ids

    # Uninitialized variable above loop
    uninit_finding = Finding(
        title="Uninitialized variable system_prompt used in loop causes UnboundLocalError",
        description="Variable system_prompt is not initialized before the loop and causes runtime failure.",
        location="agents.py:100",
        severity="HIGH",
        status="UNVERIFIED",
    )
    uninit_match = is_common_hallucination(uninit_finding, threshold=0.4)
    assert uninit_match is not None
    assert uninit_match.hallucination.id == "HALLUCINATION-UNINITIALIZED-VARIABLE-ABOVE-LOOP"

    # Pathlib Path.resolve() False FileNotFoundError Claim
    resolve_finding = Finding(
        title="Pathlib resolve raises FileNotFoundError on non-existent paths",
        description="pathlib.resolve() causes FileNotFoundError when path does not exist.",
        location="paths.py:42",
        severity="MEDIUM",
        status="UNVERIFIED",
    )
    resolve_match = is_common_hallucination(resolve_finding, threshold=0.4)
    assert resolve_match is not None
    assert resolve_match.hallucination.id == "HALLUCINATION-PATHLIB-RESOLVE-FILENOTFOUND"

    # Health Endpoint Version Disclosure
    health_finding = Finding(
        title="Information disclosure of version number in health endpoint",
        description="Exposing version number in health endpoint represents CWE-200.",
        location="routes/health.py:10",
        severity="LOW",
        status="UNVERIFIED",
    )
    health_match = is_common_hallucination(health_finding, threshold=0.4)
    assert health_match is not None
    assert health_match.hallucination.id == "HALLUCINATION-HEALTH-ENDPOINT-VERSION"

    # Stream Event Timestamp Leakage
    stream_finding = Finding(
        title="Timestamp leakage in SSE event stream",
        description="Leakage of timestamps in events stream reveals system clock information.",
        location="routes/stream.py:50",
        severity="LOW",
        status="UNVERIFIED",
    )
    stream_match = is_common_hallucination(stream_finding, threshold=0.4)
    assert stream_match is not None
    assert stream_match.hallucination.id == "HALLUCINATION-STREAM-EVENT-TIMESTAMP"

    # Local File Read or Bounded In-Memory Collection False CWE-400 Claim
    cwe400_finding = Finding(
        title="Uncontrolled resource consumption CWE-400 in read_text()",
        description="Using read_text() on pyproject.toml causes denial of service memory exhaustion.",
        location="commands/review.py:10",
        severity="HIGH",
        status="UNVERIFIED",
    )
    cwe400_match = is_common_hallucination(cwe400_finding, threshold=0.4)
    assert cwe400_match is not None
    assert cwe400_match.hallucination.id == "HALLUCINATION-LOCAL-FILE-OR-COLLECTION-CWE400"

    # Non-Existent AI Fixer Module & Unbounded Repair Payload Claim
    fixer_finding = Finding(
        title="Unbounded payload in repair_json_string in ai/fixer.py",
        description="ai/fixer.py repair_json_string has unbounded payload leading to memory exhaustion.",
        location="src/devops_cli/ai/fixer.py:20",
        severity="HIGH",
        status="UNVERIFIED",
    )
    fixer_match = is_common_hallucination(fixer_finding, threshold=0.4)
    assert fixer_match is not None
    assert fixer_match.hallucination.id == "HALLUCINATION-NONEXISTENT-FIXER-PAYLOAD"

    # CI Workflow Allow Blocked Merge State False Bypass Claim
    ci_finding = Finding(
        title="Insecure bypass with --allow-blocked-state in CI",
        description="check-readiness --allow-blocked-state allows bypass of blocked merge state in CI.",
        location=".github/workflows/ci.yml:45",
        severity="HIGH",
        status="UNVERIFIED",
    )
    ci_match = is_common_hallucination(ci_finding, threshold=0.4)
    assert ci_match is not None
    assert ci_match.hallucination.id == "HALLUCINATION-CI-ALLOW-BLOCKED-STATE"


# =============================================================================
# Negative exemplars in the generation prompt
# =============================================================================


def _entry(name: str, description: str, count: int):
    """Build one claim a person judged in a review of the working directory's repository."""
    from devops_cli.ai.review.judged_claims import project_of

    return CommonHallucinationEntry(
        id=name,
        name=description,
        category=HallucinationCategory.GENERAL,
        description=description,
        resolution="Disproved against the source.",
        occurrence_count=count,
        source="person",
        judged=_judged(project=project_of(Path.cwd())),
    )


def test_the_most_frequent_false_positives_are_shown_first() -> None:
    """Recurrence is concentrated in a few entries; the tail spends tokens for nothing.

    The claims people judged most often come first: the shipped entries' counts never changed,
    51 of 53 of them 1, so recurrence never reached generation (#950).
    """
    from unittest.mock import patch

    from devops_cli.ai.review import common_hallucinations as module

    entries = [_entry("rare", "Rarely seen claim", 1), _entry("common", "Frequent claim", 99)]
    with patch.object(module, "load_common_hallucinations", return_value=entries):
        rendered = module.render_negative_exemplars(limit=1)
    assert ("Frequent claim" in rendered, "Rarely seen claim" in rendered) == (True, False)


def test_the_exemplar_block_is_bounded() -> None:
    """This is prepended to every segment for every persona, so its size is a budget."""
    from unittest.mock import patch

    from devops_cli.ai.review import common_hallucinations as module

    entries = [_entry(f"e{i}", "x" * 4000, i) for i in range(40)]
    with patch.object(module, "load_common_hallucinations", return_value=entries):
        rendered = module.render_negative_exemplars(limit=5, max_chars=100)
    assert len(rendered) < 1000


def test_an_empty_ledger_contributes_nothing() -> None:
    """A first review of an unfamiliar repository must not carry an empty heading."""
    from unittest.mock import patch

    from devops_cli.ai.review import common_hallucinations as module

    with (
        patch.object(module, "load_common_hallucinations", return_value=[]),
        patch.object(module, "_build_builtin_hallucinations", return_value=[]),
    ):
        assert module.render_negative_exemplars() == ""


def test_the_persona_prompt_carries_the_exemplars() -> None:
    """Injection is the point; rendering the block and not using it would change nothing."""
    from unittest.mock import patch

    from devops_cli.ai.review import common_hallucinations as module
    from devops_cli.ai.review import runner as runner_module

    persona = type("P", (), {"system_prompt": "You review code."})()
    with patch.object(
        module,
        "render_negative_exemplars",
        return_value="\n\n## Previously Recorded False Positives\n- A disproved claim",
    ):
        prompt = runner_module._persona_system_prompt(persona, "")
    assert "A disproved claim" in prompt


def test_the_exemplars_survive_alongside_project_conventions() -> None:
    """A target that ships an AGENTS.md takes a different branch; both must carry them."""
    from unittest.mock import patch

    from devops_cli.ai.review import common_hallucinations as module
    from devops_cli.ai.review import runner as runner_module

    persona = type("P", (), {"system_prompt": "You review code."})()
    with patch.object(module, "render_negative_exemplars", return_value="\n- A disproved claim"):
        prompt = runner_module._persona_system_prompt(persona, "# Conventions")
    assert ("A disproved claim" in prompt, "# Conventions" in prompt) == (True, True)
