"""Tests for syntax-aware secret masking in review and analysis callers (#889)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.analyze.scanner import detect_syntax, syntax_from_language
from devops_cli.ai.review.cited_code import record_cited_code
from devops_cli.review.analysis import _build_anchor_excerpt
from devops_cli.review.anchors import ToolAnchor
from devops_cli.review.finding import Finding
from tests.support.builders import make_finding


def test_syntax_from_language_distinguishes_code_and_data() -> None:
    """Programming languages classify as code syntax; markup, config and text classify as data."""
    assert syntax_from_language("python") == "code"
    assert syntax_from_language("javascript") == "code"
    assert syntax_from_language("typescript") == "code"
    assert syntax_from_language("go") == "code"
    assert syntax_from_language("rust") == "code"
    assert syntax_from_language("c") == "code"
    assert syntax_from_language("cpp") == "code"
    assert syntax_from_language("java") == "code"
    assert syntax_from_language("shell") == "code"
    assert syntax_from_language("bash") == "code"

    assert syntax_from_language("env") == "data"
    assert syntax_from_language("yaml") == "data"
    assert syntax_from_language("json") == "data"
    assert syntax_from_language("toml") == "data"
    assert syntax_from_language("ini") == "data"
    assert syntax_from_language("markdown") == "data"
    assert syntax_from_language("text") == "data"
    assert syntax_from_language("plaintext") == "data"
    assert syntax_from_language("dockerfile") == "data"
    assert syntax_from_language(None) == "data"


def test_detect_syntax_from_file_paths(tmp_path: Path) -> None:
    """Paths classify as code or data syntax according to their file extensions and manifest names."""
    assert detect_syntax("app.py") == "code"
    assert detect_syntax("service.ts") == "code"
    assert detect_syntax("worker.go") == "code"
    assert detect_syntax("script.sh") == "code"

    assert detect_syntax(".env") == "data"
    assert detect_syntax("config.env") == "data"
    assert detect_syntax("values.yaml") == "data"
    assert detect_syntax("settings.json") == "data"
    assert detect_syntax("README.md") == "data"
    assert detect_syntax("Dockerfile") == "data"


def test_review_masks_python_and_env_files_by_their_own_syntax(tmp_path: Path) -> None:
    """A review of one Python file and one env file masks each by its own syntax without a model."""
    tree = tmp_path / "repo"
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "pyproject.toml").write_text("[project]\nname = 'target'\n", encoding="utf-8")
    (tree / "app.py").write_text("password = cfg.db_password\n", encoding="utf-8")
    (tree / ".env").write_text("password = settings.Hunter22\n", encoding="utf-8")

    findings = [
        make_finding(
            saved=True,
            severity="HIGH",
            location="app.py:1",
            title="Python configuration expression",
            category="configuration",
        ),
        make_finding(
            saved=True,
            severity="HIGH",
            location=".env:1",
            title="Env setting check",
            category="configuration",
        ),
    ]

    record_cited_code(findings, lambda p: tree / p, tree)

    assert findings[0].cited_code is not None
    assert findings[0].cited_code.excerpt == "password = cfg.db_password"

    assert findings[1].cited_code is not None
    assert findings[1].cited_code.excerpt == "password=<masked-password>"


def test_anchor_excerpts_mask_by_file_syntax() -> None:
    """Anchor excerpts in group analysis preserve code expressions in source files and mask in data files."""
    f_py = Finding(
        anchor=ToolAnchor(run_id="r1", result_index=0, rule_id="py-rule"),
        tool="semgrep",
        rule_id="py-rule",
        path="app.py",
        line=1,
        message="Hardcoded password candidate",
        severity="HIGH",
        severity_derivation="tool-native",
        fingerprint_v2="py-1",
    )
    f_env = Finding(
        anchor=ToolAnchor(run_id="r2", result_index=0, rule_id="env-rule"),
        tool="semgrep",
        rule_id="env-rule",
        path=".env",
        line=1,
        message="Hardcoded password candidate",
        severity="HIGH",
        severity_derivation="tool-native",
        fingerprint_v2="env-1",
    )

    excerpt_py = _build_anchor_excerpt(f_py, "password = cfg.db_password\n", context_lines=0)
    excerpt_env = _build_anchor_excerpt(f_env, "password = settings.Hunter22\n", context_lines=0)

    assert excerpt_py is not None
    assert excerpt_py.excerpt == "password = cfg.db_password"

    assert excerpt_env is not None
    assert excerpt_env.excerpt == "password=<masked-password>"


def test_outlines_masking_preserves_code_syntax(monkeypatch) -> None:
    """Outline metadata enhancement and pseudocode generation pass code syntax for programming languages."""
    from devops_cli.ai.analyze.outlines import _enhance_file_metadata_with_ai

    captured_prompt = None

    class FakeClient:
        def chat_messages(self, system_prompt: str, messages: list) -> str:
            nonlocal captured_prompt
            captured_prompt = messages[0].content
            return '{"overview": "test", "domain_concepts": []}'

    _enhance_file_metadata_with_ai(
        rel_path="src/main.py",
        content="password = cfg.db_password\n",
        lang="python",
        static_symbols=[],
        ai_client=FakeClient(),
    )

    assert captured_prompt is not None
    assert "password = cfg.db_password" in captured_prompt
