"""Tests for code-scanning alert handling during roadmap refine (#5258).

When an item names a code-scanning alert, refine reads the alert (rule ID, rule description,
severity, path) with one GET and puts the rule text in the design evidence. The judge compares
the design with the rule text.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.github.session import get_github_session
from devops_cli.roadmap.refine.refine import (
    AcceptanceCriterion,
    QuestionAnswer,
    RefinementProposal,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stage.stage_eval_cases import DefectType, Severity
from devops_cli.roadmap.stage.stage_verify import Finding, Locator, PlanPart, Verification
from devops_cli.roadmap.stores.store import ItemField, JudgeVerdict, RefineRecordKey
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "dan-petty/devops-cli"
APP = "devops-cli-service[bot]"
CONTRIBUTOR = "CONTRIBUTOR"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tf" / "azure").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(repo, "config", key, value)
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", f"https://example.com/{REPO}.git")
    (repo / "tf" / "azure" / "main.tf").write_text(
        'resource "azurerm_kubernetes_cluster" "aks" {\n  name = "aks"\n}\n',
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture(autouse=True)
def app_login(config: Callable[..., Path]) -> str:
    config(service={"github_app": {"slug": APP.removesuffix("[bot]")}})
    return APP


class _Proposer:
    def __init__(self, proposal: RefinementProposal) -> None:
        self.proposal = proposal
        self.requests: list[dict[str, Any]] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        import json

        try:
            self.requests.append(json.loads(prompt))
        except Exception:
            pass
        return self.proposal


class _Verifier:
    def __init__(self, *findings: Finding) -> None:
        self.findings = list(findings)
        self.requests: list[dict[str, Any]] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        import json

        try:
            self.requests.append(json.loads(prompt))
        except Exception:
            pass
        return Verification(findings=self.findings)


def test_alert_number_of_extracts_alert_number() -> None:
    from devops_cli.roadmap.refine.refine import alert_number_of

    assert (
        alert_number_of(
            "Trivy reports misconfiguration.\n\nOpen alerts:\n- alert 213: https://github.com/dan-petty/devops-cli/security/code-scanning/213\n"
        )
        == 213
    )
    assert alert_number_of("Fix code-scanning/alerts/456 in module") == 456
    assert alert_number_of("Security alert in code-scanning/789") == 789
    assert alert_number_of("Regular issue without any security alert") is None


def test_read_code_scanning_alert_reads_with_one_get(github_api: GitHubApiFake) -> None:
    from devops_cli.security.alert_filer import read_alert

    alert_raw = {
        "number": 213,
        "tool": {"name": "Trivy-config"},
        "rule": {
            "id": "AZU-0041",
            "description": "Ensure AKS has an API Server Authorized IP Ranges enabled",
            "severity": "error",
            "security_severity_level": "critical",
        },
        "most_recent_instance": {
            "location": {"path": "tf/azure/main.tf"},
        },
    }
    github_api.route(
        "GET",
        f"/repos/{REPO}/code-scanning/alerts/213",
        github_json(alert_raw),
    )

    alert = read_alert(get_github_session(), REPO, 213)
    assert alert is not None
    assert alert.number == 213
    assert alert.rule_id == "AZU-0041"
    assert alert.rule_description == "Ensure AKS has an API Server Authorized IP Ranges enabled"
    assert alert.severity == "CRITICAL"
    assert alert.path == "tf/azure/main.tf"


def test_read_code_scanning_alert_returns_none_on_error(github_api: GitHubApiFake) -> None:
    from devops_cli.security.alert_filer import read_alert

    github_api.route(
        "GET",
        f"/repos/{REPO}/code-scanning/alerts/999",
        github_json({"message": "Not Found"}, status=404),
    )
    assert read_alert(get_github_session(), REPO, 999) is None

    github_api.route(
        "GET",
        f"/repos/{REPO}/code-scanning/alerts/998",
        github_json({"number": "invalid"}),
    )
    assert read_alert(get_github_session(), REPO, 998) is None


def test_refine_reads_alert_and_puts_rule_text_in_evidence_and_context(
    git_repo: Path, github_api: GitHubApiFake
) -> None:
    alert_raw = {
        "number": 213,
        "tool": {"name": "Trivy-config"},
        "rule": {
            "id": "AZU-0041",
            "description": "Ensure AKS has an API Server Authorized IP Ranges enabled",
            "severity": "error",
            "security_severity_level": "critical",
        },
        "most_recent_instance": {
            "location": {"path": "tf/azure/main.tf"},
        },
    }
    github_api.route(
        "GET",
        f"/repos/{REPO}/code-scanning/alerts/213",
        github_json(alert_raw),
    )

    store = InMemoryRoadmapStore(repo=REPO, is_private=True)
    body = (
        "Trivy reports a misconfiguration that no issue names.\n\n"
        "- Rule: AZU-0041\n"
        "- Path: tf/azure/main.tf\n"
        "- Severity: CRITICAL\n\n"
        "Open alerts:\n"
        "- alert 213: https://github.com/dan-petty/devops-cli/security/code-scanning/213\n"
    )
    issue_num = store.seed_issue(
        "fix(security): judge Trivy-config AZU-0041 in tf/azure/main.tf",
        body=body,
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
        author_login=APP,
        author_association=CONTRIBUTOR,
    )

    proposal = RefinementProposal(
        problem_statement="Trivy config reports AZU-0041 at tf/azure/main.tf.",
        acceptance_criteria=[
            AcceptanceCriterion(
                name="Authorized IP ranges",
                requirement="The AKS cluster SHALL set authorized IP ranges.",
                scenario="Verification",
                when="trivy scans",
                then="no AZU-0041 finding",
            )
        ],
        existing_tool="AzureRM provider supplies api_server_access_profile.",
        key_questions=[
            QuestionAnswer(
                question="Which rule does alert 213 report, and what does it require?",
                answer="Alert 213 reports AZU-0041 at CRITICAL severity on tf/azure/main.tf. The rule requires Ensure AKS has an API Server Authorized IP Ranges enabled.",
                kind="decision",
                sources=[f"https://github.com/{REPO}/security/code-scanning/213"],
            )
        ],
    )
    proposer = _Proposer(proposal)
    verifier = _Verifier()

    plan = plan_refine(
        store, repo=REPO, source=git_repo, item_number=issue_num, model=proposer, verifier=verifier
    )
    apply_refine(store, plan)

    # 1. Proposer received alert info in request / context
    assert len(proposer.requests) >= 1
    req = proposer.requests[0]
    assert "alert" in req or "Ensure AKS has an API Server Authorized IP Ranges enabled" in req.get(
        "context", ""
    )

    # 2. Refined item's new body holds the rule description in design evidence (Key questions)
    item = store.item(issue_num)
    assert item is not None
    assert "Ensure AKS has an API Server Authorized IP Ranges enabled" in item.body

    # 3. Verifier received the rule description in the body of VerificationInput
    assert len(verifier.requests) >= 1
    verify_req = verifier.requests[0]
    assert "Ensure AKS has an API Server Authorized IP Ranges enabled" in verify_req["body"]


def test_refine_judge_refuses_proposal_addressing_wrong_alert_rule(
    git_repo: Path, github_api: GitHubApiFake
) -> None:
    alert_raw = {
        "number": 213,
        "tool": {"name": "Trivy-config"},
        "rule": {
            "id": "AZU-0041",
            "description": "Ensure AKS has an API Server Authorized IP Ranges enabled",
            "severity": "error",
            "security_severity_level": "critical",
        },
        "most_recent_instance": {
            "location": {"path": "tf/azure/main.tf"},
        },
    }
    github_api.route(
        "GET",
        f"/repos/{REPO}/code-scanning/alerts/213",
        github_json(alert_raw),
    )

    store = InMemoryRoadmapStore(repo=REPO, is_private=True)
    body = (
        "Trivy reports a misconfiguration that no issue names.\n\n"
        "- Rule: AZU-0041\n"
        "- Path: tf/azure/main.tf\n"
        "- Severity: CRITICAL\n\n"
        "Open alerts:\n"
        "- alert 213: https://github.com/dan-petty/devops-cli/security/code-scanning/213\n"
    )
    issue_num = store.seed_issue(
        "fix(security): judge Trivy-config AZU-0041 in tf/azure/main.tf",
        body=body,
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
        author_login=APP,
        author_association=CONTRIBUTOR,
    )

    # Proposal mistakenly plans network_policy = "azure" (the fix for AZU-0043)
    wrong_proposal = RefinementProposal(
        problem_statement="The AKS cluster sets no network policy.",
        acceptance_criteria=[
            AcceptanceCriterion(
                name="Network policy",
                requirement="The cluster SHALL set network policy azure.",
                scenario="Verification",
                when="trivy scans",
                then="network policy is set",
            )
        ],
        existing_tool="AzureRM provider supplies network_policy.",
    )
    proposer = _Proposer(wrong_proposal)
    # The verifier detects that the problem statement contradicts the alert rule in body
    mismatch_finding = Finding(
        type=DefectType.FALSE_PREMISE,
        severity=Severity.MAJOR,
        where=Locator(part=PlanPart.PROPOSAL, section="problem_statement"),
        problem="The plan addresses network policy, but alert 213 requires API Server Authorized IP Ranges.",
        quote="The AKS cluster sets no network policy.",
    )
    verifier = _Verifier(mismatch_finding)

    plan = plan_refine(
        store, repo=REPO, source=git_repo, item_number=issue_num, model=proposer, verifier=verifier
    )
    apply_refine(store, plan)

    item = store.item(issue_num)
    assert item is not None
    assert item.status == "New"
    assert item.job_record.get(RefineRecordKey.JUDGE) == JudgeVerdict.REFUSED.value
    assert item.job_record.get(RefineRecordKey.FAILED_CHECK) == "judge_refused"


def test_refine_judge_injects_alert_rule_description_into_verification_body(
    git_repo: Path,
) -> None:
    from devops_cli.roadmap.refine.refine_judge import judge
    from devops_cli.security.alert_filer import CodeScanningAlert

    alert = CodeScanningAlert(
        number=213,
        tool_name="Trivy-config",
        rule_id="AZU-0041",
        rule_description="Ensure AKS has an API Server Authorized IP Ranges enabled",
        severity_level="critical",
        path="tf/azure/main.tf",
    )
    store = InMemoryRoadmapStore(repo=REPO, is_private=True)
    issue_num = store.seed_issue(
        "fix(security): judge Trivy-config AZU-0041 in tf/azure/main.tf",
        body="Some body text without the rule description.",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
        author_login=APP,
        author_association=CONTRIBUTOR,
    )
    item = store.item(issue_num)
    assert item is not None

    proposal = RefinementProposal(
        problem_statement="Trivy config reports AZU-0041 at tf/azure/main.tf.",
        acceptance_criteria=[
            AcceptanceCriterion(
                name="Authorized IP ranges",
                requirement="The AKS cluster SHALL set authorized IP ranges.",
                scenario="Verification",
                when="trivy scans",
                then="no AZU-0041 finding",
            )
        ],
        existing_tool="AzureRM provider supplies api_server_access_profile.",
    )
    verifier = _Verifier()
    verdict, _findings = judge(
        lambda: verifier,
        item,
        item.body,
        proposal,
        git_repo,
        unchanged=False,
        repo=REPO,
        alert=alert,
    )
    assert verdict is JudgeVerdict.APPROVED
    assert len(verifier.requests) == 1
    assert (
        "Ensure AKS has an API Server Authorized IP Ranges enabled" in verifier.requests[0]["body"]
    )
