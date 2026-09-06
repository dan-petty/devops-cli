"""Unit tests for deterministic programmatic functions replacing brittle AI/LLM prompt instructions."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.verification import (
    _apply_single_finding_verification,
    _deterministic_pre_verification,
)
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    canonicalize_finding_location,
    derive_recommendation,
    sanitize_finding_text,
)


class TestTextAndLocationSanitization:
    """Test programmatic cleaning of prompt boilerplate, criteria leakage, and locations."""

    def test_sanitize_finding_text_strips_criteria_and_headers(self) -> None:
        """Prompt criteria and instruction headers must be stripped from text fields."""
        raw = (
            "Provide fix: Replace hardcoded token.\n\n"
            "Verification criteria: The string 'abc' is present in code.\n"
            "Invalidation criteria: The token is rotated or loaded from env."
        )
        cleaned = sanitize_finding_text(raw)
        assert "Verification criteria:" not in cleaned
        assert "Invalidation criteria:" not in cleaned
        assert "Provide fix:" not in cleaned
        assert "Replace hardcoded token." in cleaned

    def test_canonicalize_location_markdown_and_links(self) -> None:
        """Markdown links, anchors, and messy syntax must normalize to path:line format."""
        assert (
            canonicalize_finding_location("[src/main.py:10-20](file:///src/main.py)")
            == "src/main.py:10-20"
        )
        assert canonicalize_finding_location("`src/utils.py#L42`") == "src/utils.py:42"
        assert canonicalize_finding_location("src/core.py, line 15") == "src/core.py:15"
        assert canonicalize_finding_location("src/api.py: 30-10") == "src/api.py:10-30"

    def test_canonicalize_location_rejects_prompt_example_placeholders(self) -> None:
        """Literal placeholders copied from prompt templates must be discarded."""
        assert canonicalize_finding_location("path/to/file.ext:start-end") == ""
        assert canonicalize_finding_location("filename.ext:1-10") == ""
        assert canonicalize_finding_location("src/file.py:42-55") == ""

    def test_finding_model_auto_sanitizes_title_and_description(self) -> None:
        """Constructing a Finding must automatically clean title, description, and location."""
        f = Finding(
            title="Title: Hardcoded Secret In Mock File Verification criteria: present",
            location="[tests/test_auth.py:25-30](file:///tests/test_auth.py)",
            description="Found secret token. Invalidation criteria: env var used.",
            severity="HIGH",
        )
        assert not f.title.startswith("Title:")
        assert "Verification criteria:" not in f.title
        assert "Invalidation criteria:" not in f.description
        assert f.location == "tests/test_auth.py:25-30"

    def test_canonicalize_location_rejects_markdown_headers_and_stars(self) -> None:
        """Markdown asterisks, bold syntax, or section headers should not be parsed as locations."""
        assert canonicalize_finding_location("**") == ""
        assert canonicalize_finding_location("***") == ""
        assert canonicalize_finding_location("## Security Review") == ""
        assert canonicalize_finding_location("---") == ""
        assert canonicalize_finding_location("### 1. Location") == ""

    def test_canonicalize_location_preserves_valid_paths_and_targets(self) -> None:
        """Canonical paths, lockfile package targets, and embedded locations must be preserved."""
        assert (
            canonicalize_finding_location("src/devops_cli/ai/context_budget.py:20-21")
            == "src/devops_cli/ai/context_budget.py:20-21"
        )
        assert canonicalize_finding_location("uv.lock:jinja2") == "uv.lock:jinja2"
        assert (
            canonicalize_finding_location(
                "In file `src/devops_cli/commands/vault.py:10-25` we found"
            )
            == "src/devops_cli/commands/vault.py:10-25"
        )

    def test_sanitize_finding_text_strips_approvals_and_conversational_filler(self) -> None:
        """Conversational approvals ('Good. But ...') and pure praise must be scrubbed."""
        assert (
            sanitize_finding_text(
                "Good. But potential race condition: known_hosts file may be modified concurrently."
            )
            == "Potential race condition: known_hosts file may be modified concurrently."
        )
        assert (
            sanitize_finding_text("The function uses write_file for write_bytes_file. Good.") == ""
        )
        assert sanitize_finding_text("No issues found in this module. Looks solid.") == ""

    def test_finding_is_empty_filters_markdown_garbage_and_praise(self) -> None:
        """Findings with punctuation locations or conversational praise must be marked empty."""
        f_garbage = Finding(
            severity="MEDIUM",
            location="**",
            title="Security Review - Principal DevSecOps Engineer",
            description="The generate command accepts an output_dir option...",
        )
        assert f_garbage.is_empty is True

        f_praise = Finding(
            severity="MEDIUM",
            location="src/devops_cli/output/file_writer.py:1-60",
            title="The function uses write_file for write_bytes_file. Good.",
            description="The function uses write_file for write_bytes_file. Good.",
        )
        assert f_praise.is_empty is True


class TestRecommendationDerivation:
    """Test deterministic programmatic calculation of merge recommendations."""

    def test_empty_findings_recommends_approve(self) -> None:
        """Zero findings must always result in APPROVE."""
        assert derive_recommendation([]) == "APPROVE"
        res = ReviewResult(findings=[], recommendation="REQUEST CHANGES")
        assert res.recommendation == "APPROVE"

    def test_critical_finding_recommends_block(self) -> None:
        """Any reportable CRITICAL finding must enforce BLOCK."""
        f = Finding(
            severity="CRITICAL",
            location="src/auth.py:10",
            title="RCE in parser",
            description="Unsafe deserialization",
        )
        assert derive_recommendation([f]) == "BLOCK"
        res = ReviewResult(findings=[f], recommendation="APPROVE")
        assert res.recommendation == "BLOCK"

    def test_high_or_medium_finding_recommends_request_changes(self) -> None:
        """Non-critical reportable findings must enforce REQUEST CHANGES."""
        f = Finding(
            severity="HIGH",
            location="src/db.py:20",
            title="Missing transaction rollback",
            description="Potential state leak",
        )
        assert derive_recommendation([f]) == "REQUEST CHANGES"
        res = ReviewResult(findings=[f], recommendation="BLOCK")
        assert res.recommendation == "REQUEST CHANGES"

    def test_invalidated_or_mitigated_findings_do_not_block_approval(self) -> None:
        """Invalidated or mitigated findings must not block merge approval."""
        f1 = Finding(
            severity="CRITICAL",
            location="tests/test_auth.py:10",
            title="Hardcoded test token",
            description="Mock credential in test",
            status="INVALIDATED",
            reportable=False,
        )
        f2 = Finding(
            severity="HIGH",
            location="src/dev.py:10",
            title="Dev mode port",
            description="Local port",
            status="MITIGATED",
            reportable=False,
        )
        assert derive_recommendation([f1, f2]) == "APPROVE"
        res = ReviewResult(findings=[f1, f2])
        assert res.recommendation == "APPROVE"


class TestPreservationOfValidFindings:
    """Verify that heuristic checks do not invalidate valid findings or validate invalid findings."""

    def test_valid_findings_in_test_files_are_not_invalidated(self, tmp_path: Path) -> None:
        """Genuine secret leak or vulnerability in test code must NOT be heuristically invalidated."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_api.py"
        test_file.write_text('REAL_AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

        f = Finding(
            severity="CRITICAL",
            location=f"tests/{test_file.name}:1",
            title="Hardcoded AWS Secret Key leaked in test file",
            description="Actual production secret committed to repository.",
        )
        res = _deterministic_pre_verification(f, repo_root=tmp_path)
        assert res.status != "INVALIDATED"
        assert res.status == "UNVERIFIED"

    def test_valid_findings_in_kustomizations_are_not_invalidated(self, tmp_path: Path) -> None:
        """Namespace misconfiguration in kustomization must NOT be heuristically invalidated."""
        k8s_dir = tmp_path / "k8s"
        k8s_dir.mkdir()
        kust_file = k8s_dir / "kustomization.yaml"
        kust_file.write_text("namespace: invalid-prod-namespace\n", encoding="utf-8")

        f = Finding(
            severity="HIGH",
            location=f"k8s/{kust_file.name}:1",
            title="Invalid namespace declaration in Kustomization",
            description="The specified namespace violates cluster naming policy.",
        )
        res = _deterministic_pre_verification(f, repo_root=tmp_path)
        assert res.status != "INVALIDATED"

    def test_valid_findings_in_terraform_outputs_are_not_invalidated(self, tmp_path: Path) -> None:
        """Command injection in outputs.tf must NOT be heuristically invalidated."""
        tf_file = tmp_path / "outputs.tf"
        tf_file.write_text(
            'output "exec" {\n  value = "sh -c \'${var.user_input}\'"\n}\n',
            encoding="utf-8",
        )
        f = Finding(
            severity="CRITICAL",
            location=f"{tf_file.name}:2",
            title="Command injection in Terraform output expression",
            description="Unsanitized user variable interpolated into shell execution.",
        )
        res = _deterministic_pre_verification(f, repo_root=tmp_path)
        assert res.status != "INVALIDATED"

    def test_unverified_finding_does_not_default_to_verified(self) -> None:
        """Verification payload omitting 'verified' must NOT default to VERIFIED."""
        f = Finding(
            severity="HIGH",
            location="src/app.py:10",
            title="Unchecked input",
            description="Missing validation",
        )
        # LLM returns empty dictionary or omits 'verified'
        updated = _apply_single_finding_verification(f, {}, now_iso="2026-09-03T00:00:00Z")
        assert updated.verified is False
        assert updated.status == "UNVERIFIED"
        assert updated.reportable is False
