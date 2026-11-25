"""Production readiness row map, readers, and review integration (#5537)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

from devops_cli.config.commands import BIN_DEVOPS, BIN_SCORECARD
from devops_cli.config.settings import load_settings
from devops_cli.roadmap.project_review.data import (
    Fact,
    FactStatus,
    ReviewData,
    ReviewWindow,
    WindowKind,
)
from devops_cli.roadmap.project_review.readiness import (
    READINESS_ROWS,
    CheckKind,
    ReadinessRowSpec,
    ReadinessScope,
    ReadinessState,
    collect_readiness,
    evaluate_repository_readiness,
    parse_scorecard_json,
    planned_readiness,
)
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import GitHubApiFake, github_json, route_file
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import REPO_ROOT

GUIDELINE = REPO_ROOT / "docs" / "guidelines" / "production-readiness.md"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
_TABLE_ROW = re.compile(
    r"^\|\s*(?P<id>(?:OWN|SLO|INC|REL|SEC|ACC|DATA|CAP|DEP|EVD)-\d+)\s*\|"
    r"\s*[^|]+\|\s*(?P<scope>[^|]+)\|\s*(?P<level>[^|]+)\|\s*(?P<measured>[^|]+)\|"
)
_SC_PATTERN = re.compile(r"SC\s+((?:`[^`]+`(?:\s*,\s*)?)+)")
_KL_PATTERN = re.compile(r"kube-linter\s+((?:`[^`]+`(?:\s*,\s*)?)+)")
_BACKTICK = re.compile(r"`([^`]+)`")
_CMD_PREFIXES = ("devops ", "kubectl ", "promtool ", "amtool ")
_ISSUE_REF = re.compile(r"#\d+")
_RECORDED_SCORECARD = {
    "date": "2026-11-24T00:00:00Z",
    "repo": {"name": "github.com/example/service-a", "commit": "a" * 40},
    "score": 7.5,
    "checks": [
        {"name": "Branch-Protection", "score": 10, "reason": "branch protection enabled"},
        {"name": "Code-Review", "score": 0, "reason": "no required reviews"},
        {"name": "License", "score": 10, "reason": "license file detected"},
        {"name": "Security-Policy", "score": 5, "reason": "security policy partial"},
        {"name": "SAST", "score": 10, "reason": "CodeQL enabled"},
        {"name": "CI-Tests", "score": 10, "reason": "CI runs on PRs"},
        {"name": "Pinned-Dependencies", "score": 6, "reason": "some unpinned deps"},
        {"name": "Vulnerabilities", "score": 10, "reason": "0 vulnerabilities"},
        {"name": "Token-Permissions", "score": 10, "reason": "read-only permissions"},
        {"name": "Dangerous-Workflow", "score": 10, "reason": "no dangerous patterns"},
        {"name": "Dependency-Update-Tool", "score": 10, "reason": "Renovate enabled"},
        {"name": "Signed-Releases", "score": 0, "reason": "unsigned release assets"},
        {"name": "SBOM", "score": 10, "reason": "SBOM generated"},
        {"name": "CII-Best-Practices", "score": 0, "reason": "no badge"},
        {"name": "Maintained", "score": 10, "reason": "active commits"},
    ],
}


def _state(fact: Fact) -> str:
    """Extract the readiness state string from a `Fact.value` mapping."""
    assert isinstance(fact.value, dict)
    return str(fact.value["state"])


def _guideline_rows() -> list[dict[str, Any]]:
    """Parse every readiness table row from `docs/guidelines/production-readiness.md`."""
    rows: list[dict[str, Any]] = []
    for line in GUIDELINE.read_text(encoding="utf-8").splitlines():
        match = _TABLE_ROW.match(line)
        if not match:
            continue
        measured = match.group("measured").strip()
        sc = tuple(
            item for block in _SC_PATTERN.findall(measured) for item in _BACKTICK.findall(block)
        )
        kl = tuple(
            item for block in _KL_PATTERN.findall(measured) for item in _BACKTICK.findall(block)
        )
        cmds = tuple(code for code in _BACKTICK.findall(measured) if code.startswith(_CMD_PREFIXES))
        rows.append(
            {
                "id": match.group("id"),
                "scope": match.group("scope").strip(),
                "level": match.group("level").strip(),
                "measured": measured,
                "scorecard": sc,
                "kube_linter": kl,
                "commands": cmds,
                "manual": "`manual`" in measured,
            }
        )
    return rows


def test_map_covers_every_guideline_row_level_and_scope() -> None:
    expected = _guideline_rows()
    by_id = {entry.id: entry for entry in READINESS_ROWS}

    assert len(READINESS_ROWS) == len(expected) == 91
    assert [entry.id for entry in READINESS_ROWS] == [row["id"] for row in expected]
    for row in expected:
        entry = by_id[row["id"]]
        assert (entry.scope.value, entry.level) == (row["scope"], row["level"]), row["id"]


def test_map_matches_measured_by_checks_and_commands() -> None:
    expected = _guideline_rows()
    by_id = {entry.id: entry for entry in READINESS_ROWS}

    for row in expected:
        entry = by_id[row["id"]]
        assert entry.scorecard_checks == row["scorecard"], row["id"]
        assert entry.kube_linter_checks == row["kube_linter"], row["id"]
        assert entry.commands == row["commands"], row["id"]
        assert entry.is_manual is row["manual"], row["id"]


def test_map_holds_no_issue_number_or_gap_table_fields() -> None:
    for entry in READINESS_ROWS:
        assert not hasattr(entry, "gap_table")
        assert not hasattr(entry, "issue_number")
        assert not hasattr(entry, "issues")
        payload = json.dumps(
            {
                "id": entry.id,
                "level": entry.level,
                "definition": entry.definition,
                "checks": list(entry.scorecard_checks),
                "commands": list(entry.commands),
                "files": list(entry.files),
            }
        )
        assert not _ISSUE_REF.search(payload), entry.id
        assert "dan-petty/" not in payload, entry.id


def test_scorecard_json_maps_to_row_states_and_sources(
    process_fake: ProcessFake,
) -> None:
    parsed = parse_scorecard_json(_RECORDED_SCORECARD)
    assert parsed["Branch-Protection"].state is ReadinessState.MET
    assert parsed["Security-Policy"].state is ReadinessState.PARTLY_MET
    assert parsed["Code-Review"].state is ReadinessState.NOT_MET

    class _EmptySession:
        def pages(self, path: str, *, max_pages: int | None = None) -> Any:
            return iter([])

    report, is_private = evaluate_repository_readiness(
        "example/service-a",
        session=_EmptySession(),
        now=NOW,
        scorecard_data=_RECORDED_SCORECARD,
    )

    assert is_private is False
    by_id = {fact.id: fact for fact in report.facts}
    assert by_id["REL-1"].value == {
        "state": ReadinessState.MET.value,
        "scope": "Repo",
        "level": "Required",
    }
    assert "Branch-Protection" in by_id["REL-1"].source
    assert _state(by_id["REL-3"]) == ReadinessState.NOT_MET.value
    assert _state(by_id["SEC-1"]) == ReadinessState.PARTLY_MET.value
    assert _state(by_id["OWN-2"]) == ReadinessState.PARTLY_MET.value


def test_scorecard_reader_runs_pinned_binary_for_service_and_infra_repos(
    config: Callable[..., Path],
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
) -> None:
    from devops_cli.github.session import get_github_session

    config(
        service={"repos": ["example/svc-a", "example/svc-b"]},
        infra={"repos": [{"repo": "example/infra-a"}]},
    )
    for repo in ("example/svc-a", "example/svc-b", "example/infra-a"):
        github_api.route("GET", f"/repos/{repo}", github_json({"private": False}))
    process_fake.answer(
        lambda call: call.argv[0] == BIN_SCORECARD and "--format" in call.argv,
        ProcessAnswer(stdout=json.dumps(_RECORDED_SCORECARD)),
    )

    report = collect_readiness(load_settings(), session=get_github_session(), now=NOW)

    scorecard_calls = [call.argv for call in process_fake.calls if call.argv[0] == BIN_SCORECARD]
    assert len(scorecard_calls) == 3
    for repo in ("example/svc-a", "example/svc-b", "example/infra-a"):
        assert any(
            "--format" in argv and "json" in argv and f"github.com/{repo}" in " ".join(argv)
            for argv in scorecard_calls
        )
    assert [r.repo for r in report.repositories] == [
        "example/svc-a",
        "example/svc-b",
        "example/infra-a",
    ]


def test_file_rows_query_github_contents_at_ref(
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
) -> None:
    from devops_cli.github.session import get_github_session

    repo = "example/service-a"
    ref = "feat/launch-branch"
    github_api.route("GET", f"/repos/{repo}", github_json({"private": False}))
    route_file(
        github_api,
        repo,
        "AGENTS.md",
        ref,
        "## Where to look\nSee [index](docs/guidelines/index.md).\n",
    )
    route_file(github_api, repo, "CODEOWNERS", ref, "* @example/maintainers\n")
    route_file(github_api, repo, "openspec/config.yaml", ref, "schema: spec-driven\n")
    route_file(github_api, repo, "README.md", ref, "# Example\n")
    route_file(github_api, repo, "CONTRIBUTING.md", ref, "# Contributing\n")
    route_file(github_api, repo, "CHANGELOG.md", ref, "# Changelog\n")

    custom_rows = (
        ReadinessRowSpec(
            id="OWN-7",
            scope=ReadinessScope.REPO,
            level="Recommended",
            kind=CheckKind.FILE,
            files=("AGENTS.md",),
            definition="AGENTS guideline link.",
        ),
        ReadinessRowSpec(
            id="FILE-CO",
            scope=ReadinessScope.REPO,
            level="Required",
            kind=CheckKind.FILE,
            files=("CODEOWNERS",),
            definition="CODEOWNERS exists.",
        ),
        ReadinessRowSpec(
            id="FILE-OS",
            scope=ReadinessScope.REPO,
            level="Required",
            kind=CheckKind.FILE,
            files=("openspec/config.yaml",),
            definition="OpenSpec config exists.",
        ),
    )

    report, _ = evaluate_repository_readiness(
        repo,
        session=get_github_session(),
        now=NOW,
        ref=ref,
        rows=custom_rows,
    )

    encoded_ref = urlencode({"ref": ref})
    assert f"GET https://api.github.com/repos/{repo}/contents/AGENTS.md?{encoded_ref}" in (
        github_api.requested
    )
    assert f"GET https://api.github.com/repos/{repo}/contents/CODEOWNERS?{encoded_ref}" in (
        github_api.requested
    )
    assert (
        f"GET https://api.github.com/repos/{repo}/contents/openspec/config.yaml?{encoded_ref}"
        in github_api.requested
    )
    for fact in report.facts:
        assert fact.value == {
            "state": ReadinessState.MET.value,
            "scope": "Repo",
            "level": custom_rows[[r.id for r in custom_rows].index(fact.id)].level,
        }
        assert fact.source == "github"
        assert fact.read_at == NOW


def test_command_row_runs_devops_command_and_maps_json_output(
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
) -> None:
    from devops_cli.github.session import get_github_session

    repo = "example/service-a"
    github_api.route("GET", f"/repos/{repo}", github_json({"private": False}))
    process_fake.answer(
        lambda call: call.argv[:4] == (BIN_DEVOPS, "repos", "onboard", repo),
        ProcessAnswer(stdout=json.dumps({"state": "met", "failing": False})),
    )
    rows = (
        ReadinessRowSpec(
            id="OWN-6",
            scope=ReadinessScope.REPO,
            level="Required for a repository in `service.repos`",
            kind=CheckKind.COMMAND,
            commands=("devops repos onboard <owner>/<name> --plan",),
            definition="Onboarding prerequisites.",
        ),
    )

    report, _ = evaluate_repository_readiness(
        repo,
        session=get_github_session(),
        now=NOW,
        rows=rows,
    )

    assert any(
        call.argv[:5] == (BIN_DEVOPS, "repos", "onboard", repo, "--plan")
        for call in process_fake.calls
    )
    fact = report.facts[0]
    assert _state(fact) == ReadinessState.MET.value
    assert "devops repos onboard" in fact.source


@pytest.mark.usefixtures("refuse_requests")
def test_manual_row_gets_not_readable_and_sends_no_request(
    process_fake: ProcessFake,
) -> None:
    class _CountingSession:
        def __init__(self) -> None:
            self.calls = 0

        def pages(self, path: str, *, max_pages: int | None = None) -> Any:
            self.calls += 1
            return iter([])

    session = _CountingSession()
    rows = (
        ReadinessRowSpec(
            id="OWN-4",
            scope=ReadinessScope.BOTH,
            level="Recommended",
            kind=CheckKind.MANUAL,
            is_manual=True,
            definition="ADRs.",
        ),
    )

    report, _ = evaluate_repository_readiness(
        "example/service-a",
        session=session,
        now=NOW,
        rows=rows,
    )

    fact = report.facts[0]
    assert session.calls == 0
    assert process_fake.calls == []
    assert _state(fact) == ReadinessState.NOT_READABLE.value
    assert fact.status is FactStatus.SKIPPED
    assert fact.source == "manual"
    assert fact.read_at == NOW


def test_ref_reads_branch_files_not_default_branch(
    github_api: GitHubApiFake,
) -> None:
    from devops_cli.github.session import get_github_session

    repo = "example/service-a"
    github_api.route("GET", f"/repos/{repo}", github_json({"private": False}))
    route_file(github_api, repo, "AGENTS.md", "main", "legacy instructions without table\n")
    route_file(
        github_api,
        repo,
        "AGENTS.md",
        "feat/add-guideline",
        "## Where to look\n- [Guidelines](docs/guidelines/index.md)\n",
    )
    rows = (
        ReadinessRowSpec(
            id="OWN-7",
            scope=ReadinessScope.REPO,
            level="Recommended",
            kind=CheckKind.FILE,
            files=("AGENTS.md",),
            definition="AGENTS routes to guidelines.",
        ),
    )

    branch_report, _ = evaluate_repository_readiness(
        repo, session=get_github_session(), now=NOW, ref="feat/add-guideline", rows=rows
    )
    default_report, _ = evaluate_repository_readiness(
        repo, session=get_github_session(), now=NOW, ref="main", rows=rows
    )

    assert _state(branch_report.facts[0]) == ReadinessState.MET.value
    assert _state(default_report.facts[0]) == ReadinessState.NOT_MET.value


def test_private_repo_excluded_from_shared_report_and_falls_back_to_github(
    config: Callable[..., Path],
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
) -> None:
    from devops_cli.github.session import get_github_session

    config(service={"repos": ["example/public-app", "example/private-infra"]})
    github_api.route(
        "GET",
        "/repos/example/public-app",
        github_json({"private": False, "license": {"spdx_id": "MIT"}}),
    )
    github_api.route(
        "GET",
        "/repos/example/private-infra",
        github_json({"private": True, "license": {"spdx_id": "MIT"}, "default_branch": "main"}),
    )
    github_api.route(
        "GET",
        "/repos/example/private-infra/contents/SECURITY.md",
        github_json({"type": "file", "encoding": "base64", "content": "IyBTZWN1cml0eQo="}),
    )
    github_api.route(
        "GET",
        "/repos/example/private-infra/contents/.github/renovate.json",
        github_json({"type": "file", "encoding": "base64", "content": "e30K"}),
    )
    github_api.route(
        "GET",
        "/repos/example/private-infra/contents/.github/workflows",
        github_json(
            [{"name": "codeql.yml", "path": ".github/workflows/codeql.yml", "type": "file"}]
        ),
    )
    github_api.route(
        "GET",
        "/repos/example/private-infra/rules/branches/main",
        github_json(
            [{"type": "pull_request", "parameters": {"required_approving_review_count": 1}}]
        ),
    )
    github_api.route(
        "GET",
        "/repos/example/private-infra/releases",
        github_json([{"tag_name": "v1.0.0"}]),
    )

    def _scorecard_reply(call: Any) -> ProcessAnswer:
        if "example/private-infra" in " ".join(call.argv):
            return ProcessAnswer(returncode=1, stderr="repository not accessible")
        return ProcessAnswer(stdout=json.dumps(_RECORDED_SCORECARD))

    process_fake.answer(lambda call: call.argv[0] == BIN_SCORECARD, _scorecard_reply)

    shared = collect_readiness(load_settings(), session=get_github_session(), now=NOW)
    assert [r.repo for r in shared.repositories] == ["example/public-app"]

    private_report, is_private = evaluate_repository_readiness(
        "example/private-infra",
        session=get_github_session(),
        now=NOW,
    )
    assert is_private is True
    by_id = {fact.id: fact for fact in private_report.facts}
    assert by_id["SEC-1"].source == "github"
    assert _state(by_id["SEC-1"]) == ReadinessState.MET.value
    assert by_id["REL-1"].source == "github"
    assert _state(by_id["REL-1"]) == ReadinessState.MET.value
    assert by_id["SEC-6"].source == "github"
    assert _state(by_id["SEC-6"]) == ReadinessState.MET.value


@pytest.mark.usefixtures("refuse_requests")
def test_dry_run_and_dynamic_settings_send_no_requests(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    process_fake: ProcessFake,
) -> None:
    config(service={"repos": ["example/dynamic-one", "example/dynamic-two"]})

    planned = planned_readiness(load_settings(), ref="feat/preview")
    assert len(planned) > 0
    assert any("example/dynamic-one" in req.target for req in planned)
    assert any("example/dynamic-two" in req.target for req in planned)
    assert process_fake.calls == []

    result = cli("roadmap", "review", "run", "--ref", "feat/preview", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "example/dynamic-one" in result.stdout
    assert "example/dynamic-two" in result.stdout
    assert process_fake.calls == []


def test_cli_review_run_with_ref_prints_readiness_json(
    cli: Callable[..., Any],
    git_fake: GitFake,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_fake.replay("review_window")
    repo_dir = tmp_path / "project"
    (repo_dir / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo_dir)

    github_api.route("GET", "/repos/example/project", github_json({"private": False}))
    route_file(
        github_api,
        "example/project",
        "AGENTS.md",
        "feat/launch",
        "## Where to look\n[Index](docs/guidelines/index.md)\n",
    )
    git_fake.answer(
        lambda call: call.argv[0] == BIN_SCORECARD,
        ProcessAnswer(stdout=json.dumps(_RECORDED_SCORECARD)),
    )
    git_fake.answer(
        lambda call: call.argv[:2] == (BIN_DEVOPS, "repos"),
        ProcessAnswer(stdout=json.dumps({"state": "met"})),
    )

    result = cli("roadmap", "review", "run", "--ref", "feat/launch", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["repo"] == "example/project"
    assert payload["ref"] == "feat/launch"
    assert len(payload["facts"]) == 91
    assert any(
        fact["id"] == "OWN-7" and fact["value"]["state"] == "met" for fact in payload["facts"]
    )


def test_guideline_readiness_record_section_mentions_ref_for_launch() -> None:
    text = GUIDELINE.read_text(encoding="utf-8")
    _, _, tail = text.partition("## Readiness record")
    section, _, _ = tail.partition("\n## ")
    assert "running service" in section
    assert "--ref" in section
    assert "launch" in section


def test_review_data_model_accepts_default_and_readiness_field() -> None:
    window = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=NOW,
        end=NOW,
        previous_id=None,
    )
    data = ReviewData(repo="example/project", window=window, facts=[])
    assert data.readiness == []
