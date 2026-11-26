"""Unit tests for Kubernetes logging stack lifecycle and CLI integration."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.networking import VALID_STACKS
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.http import WebFake
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.k8s_commands import answer_helm_version

runner = CliRunner()


def test_logging_stack_definitions_and_single_shipper(
    cli: Callable[..., Any], process_fake: ProcessFake, env_tree: Path
) -> None:
    """Verify logging stack registers Loki alone (#548)."""
    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env_tree), "--dry-run")
    assert res.exit_code == 0
    details = _dry_run_details(res.output)

    release_names = tuple(details["helm_releases"])
    repo_names = tuple(
        cmd[3] for cmd in details["helm_commands"] if cmd[:3] == ["helm", "repo", "add"]
    )

    assert (release_names, repo_names) == (("loki",), ("grafana-community",))

    # The perimeter of the namespace is in the build of the Application `logging` (#6681).
    assert (
        "logging" in VALID_STACKS,
        any(label.startswith("logging: ") for label in details["path_sources"]),
    ) == (True, True)


def test_deploy_stack_installs_loki_from_the_grafana_community_chart(
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    env_tree: Path,
) -> None:
    """The logging stack of deploy-stack installs the chart `grafana-community/loki` into the
    namespace `logging` from the grafana-community repository (#1632). The version and the values
    files come from the Argo CD Application of the tree (#6060, #6680)."""
    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env_tree), "--dry-run")
    assert res.exit_code == 0
    details = _dry_run_details(res.output)

    repo_cmd = next(cmd for cmd in details["helm_commands"] if cmd[:3] == ["helm", "repo", "add"])
    upgrade_cmd = next(
        cmd for cmd in details["helm_commands"] if cmd[:3] == ["helm", "upgrade", "--install"]
    )

    chart = upgrade_cmd[5]
    namespace = upgrade_cmd[upgrade_cmd.index("--namespace") + 1]
    repo_url = repo_cmd[4]

    assert (
        chart,
        namespace,
        repo_url,
    ) == (
        "grafana-community/loki",
        "logging",
        "https://grafana-community.github.io/helm-charts",
    )


def _without_version(commands: list[list[str]]) -> list[list[str]]:
    """`commands` with the `--version` option and its value left out: the version comes from the
    Argo CD Application of the tree (#6060)."""
    return [
        [arg for i, arg in enumerate(cmd) if "--version" not in (arg, cmd[i - 1] if i else "")]
        for cmd in commands
    ]


def _dry_run_details(output: str) -> dict[str, Any]:
    """The details of a dry-run result, after its heading."""
    details: dict[str, Any] = json.loads(output[output.index("{") :])["details"]
    return details


def test_deploy_stack_dry_run_lists_the_helm_commands_of_the_logging_stack(
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    env_tree: Path,
) -> None:
    """The logging stack dry run lists helm repo add/update and helm upgrade commands (#2469)."""
    expected_repo_cmds = [
        [
            "helm",
            "repo",
            "add",
            "grafana-community",
            "https://grafana-community.github.io/helm-charts",
        ],
        ["helm", "repo", "update"],
    ]
    base_upgrade_cmd = [
        "helm",
        "upgrade",
        "--install",
        "--take-ownership",
        "loki",
        "grafana-community/loki",
        "--namespace",
        "logging",
        "--kube-context",
        "ctx-example",
    ]

    res_wait = cli(
        "k8s",
        "deploy-stack",
        "--stack",
        "logging",
        "--k8s-dir",
        str(env_tree),
        "--context",
        "ctx-example",
        "--dry-run",
    )
    assert res_wait.exit_code == 0
    assert _without_version(_dry_run_details(res_wait.output)["helm_commands"]) == [
        *expected_repo_cmds,
        [*base_upgrade_cmd, "--wait", "--timeout", "10m"],
    ]

    res_no_wait = cli(
        "k8s",
        "deploy-stack",
        "--stack",
        "logging",
        "--k8s-dir",
        str(env_tree),
        "--context",
        "ctx-example",
        "--dry-run",
        "--no-wait",
    )
    assert res_no_wait.exit_code == 0
    assert _without_version(_dry_run_details(res_no_wait.output)["helm_commands"]) == [
        *expected_repo_cmds,
        base_upgrade_cmd,
    ]


def test_deploy_stack_dry_run_lists_the_helm_commands_that_the_real_run_starts(
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    env_tree: Path,
) -> None:
    """The dry run lists the helm repo and upgrade commands that the real run starts (#2469)."""
    ready_node = json.dumps(
        {
            "items": [
                {
                    "metadata": {"name": "node-1"},
                    "status": {"conditions": [{"type": "Ready", "status": "True"}]},
                }
            ]
        }
    )
    process_fake.answer(
        "kubectl cluster-info",
        ProcessAnswer(stdout="Kubernetes control plane is running\n"),
    )
    process_fake.answer("kubectl get nodes", ProcessAnswer(stdout=ready_node))
    answer_helm_version(process_fake, "v3.17.0")
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "repo"),
        ProcessAnswer(returncode=0, stdout="ok\n"),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "status"),
        ProcessAnswer(returncode=1, stdout="not found\n"),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "upgrade"),
        ProcessAnswer(returncode=0, stdout="Release installed\n"),
    )

    real_res = cli(
        "k8s",
        "deploy-stack",
        "--stack",
        "logging",
        "--k8s-dir",
        str(env_tree),
        "--context",
        "ctx-example",
        "--no-push-secrets",
        "--no-wait",
    )
    assert real_res.exit_code == 0

    real_helm_cmds = [
        list(call.argv)
        for call in process_fake.calls
        if call.argv[:2] in {("helm", "repo"), ("helm", "upgrade")}
    ]

    calls_before_dry_run = len(process_fake.calls)
    dry_res = cli(
        "k8s",
        "deploy-stack",
        "--stack",
        "logging",
        "--k8s-dir",
        str(env_tree),
        "--context",
        "ctx-example",
        "--dry-run",
        "--no-wait",
    )
    assert dry_res.exit_code == 0

    dry_details = _dry_run_details(dry_res.output)
    assert real_helm_cmds == dry_details["helm_commands"]

    helm_calls_during_dry_run = [
        call.argv
        for call in process_fake.calls[calls_before_dry_run:]
        if call.argv and call.argv[0] == "helm"
    ]
    assert helm_calls_during_dry_run == []


def test_deploy_logging_stack_dry_run(process_fake: ProcessFake, env_tree: Path) -> None:
    """Verify deploy-stack --stack logging with dry run."""
    set_dry_run(True)
    argv = ["deploy-stack", "--stack", "logging", "--no-push-secrets", "--k8s-dir", str(env_tree)]
    result = runner.invoke(app, argv)
    assert result.exit_code == 0
    assert "deploy-stack" in result.output
    assert "logging" in result.output


def test_teardown_logging_stack_dry_run(process_fake: ProcessFake, env_tree: Path) -> None:
    """Verify teardown-stack --stack logging with dry run."""
    set_dry_run(True)
    argv = ["teardown-stack", "--stack", "logging", "--k8s-dir", str(env_tree)]
    result = runner.invoke(app, argv)
    assert result.exit_code == 0
    assert "teardown-stack" in result.output
    assert "logging" in result.output


def test_deploy_logging_stack_live(
    cluster: FakeCluster, process_fake: ProcessFake, env_tree: Path
) -> None:
    """Verify deploy-stack --stack logging execution."""
    answer_helm_version(process_fake)
    argv = ["deploy-stack", "--stack", "logging", "--no-push-secrets", "--k8s-dir", str(env_tree)]

    result = runner.invoke(app, argv)

    installed = [
        call.argv[4]
        for call in process_fake.calls
        if call.argv[:3] == ("helm", "upgrade", "--install")
    ]
    assert (result.exit_code, installed) == (0, ["loki"])


def test_teardown_logging_stack_live(
    cluster: FakeCluster, process_fake: ProcessFake, env_tree: Path
) -> None:
    """Verify teardown-stack --stack logging execution."""
    argv = ["teardown-stack", "--stack", "logging", "--k8s-dir", str(env_tree)]

    result = runner.invoke(app, argv)

    removed = [
        call.argv[2] for call in process_fake.calls if call.argv[:2] == ("helm", "uninstall")
    ]
    assert (result.exit_code, removed) == (0, ["loki"])


def test_k8s_logs_backward_compatibility(process_fake: ProcessFake) -> None:
    """Verify devops k8s logs <pod> continues to work as expected."""
    process_fake.answer("kubectl logs", ProcessAnswer(stdout="pod logs output"))

    result = runner.invoke(app, ["logs", "my-legacy-pod", "-n", "default", "--tail", "25"])

    assert result.exit_code == 0
    assert [call.argv[:3] for call in process_fake.calls] == [("kubectl", "logs", "my-legacy-pod")]


def _serve_loki(web: WebFake, streams: list[dict[str, Any]] | None = None) -> None:
    """Answer each Loki range query with `streams`, or with no stream."""
    body = json.dumps({"data": {"result": streams or []}})
    web.serve(lambda _request: httpx2.Response(200, text=body))


def _loki_queries(web: WebFake) -> list[str]:
    """The LogQL expression of each range query that reached Loki."""
    return [
        parse_qs(urlsplit(request.url).query)["query"][0]
        for request in web.recorded
        if urlsplit(request.url).path == "/loki/api/v1/query_range"
    ]


def test_k8s_logs_logql_query_dispatch(
    config: Callable[..., Path], web: WebFake, process_fake: ProcessFake
) -> None:
    """Verify devops k8s logs '{app=\"foo\"}' routes to LogQL query engine."""
    config(loki={"url": "http://example.com:3100"})
    _serve_loki(web)

    result = runner.invoke(
        app,
        ["logs", '{app="frontend"} |= "error"', "--since", "30m", "--limit", "20"],
    )

    sent = parse_qs(urlsplit(web.recorded[0].url).query)
    assert (
        result.exit_code,
        _loki_queries(web),
        sent["since"],
        sent["limit"],
        process_fake.calls,
    ) == (0, ['{app="frontend"} |= "error"'], ["30m"], ["20"], [])


def test_k8s_logs_subcommand_query_dispatch(
    config: Callable[..., Path], web: WebFake, process_fake: ProcessFake
) -> None:
    """Verify devops k8s logs query '{app=\"foo\"}' routes to LogQL query engine."""
    config(loki={"url": "http://example.com:3100"})
    _serve_loki(web)

    result = runner.invoke(app, ["logs", "query", '{app="backend"}', "--limit", "10"])

    assert (result.exit_code, _loki_queries(web), process_fake.calls) == (
        0,
        ['{app="backend"}'],
        [],
    )


def test_k8s_logs_pod_named_tail_legacy(process_fake: ProcessFake) -> None:
    """Verify devops k8s logs tail without query argument treats tail as a pod name."""
    process_fake.answer("kubectl logs", ProcessAnswer(stdout="logs from pod tail"))

    result = runner.invoke(app, ["logs", "tail", "-n", "default"])

    assert result.exit_code == 0
    assert len(process_fake.calls) == 1
    assert "tail" in process_fake.calls[0].argv


def test_k8s_logs_logql_rejects_follow() -> None:
    """Verify devops k8s logs with LogQL query rejects --follow."""
    result = runner.invoke(app, ["logs", '{app="frontend"}', "--follow"])
    assert result.exit_code == 1
    assert "--follow" in result.output


def test_k8s_logs_empty_query_rejected() -> None:
    """Verify devops k8s logs with empty query string exits with error."""
    result = runner.invoke(app, ["logs", "--query", "   "])
    assert result.exit_code == 1
    assert "LogQL query expression is required" in result.output


def test_k8s_logs_escapes_rich_markup(config: Callable[..., Path], web: WebFake) -> None:
    """Verify log entries with Rich markup brackets are safely escaped in output."""
    config(loki={"url": "http://example.com:3100"})
    _serve_loki(
        web,
        [
            {
                "stream": {"pod": "web-pod-1"},
                "values": [
                    [
                        "1788950400000000000",
                        "[bold red]critical payload syntax error[/bold red] <xml>",
                    ]
                ],
            }
        ],
    )

    result = runner.invoke(app, ["logs", '{app="web"}'])

    assert result.exit_code == 0
    assert "[bold red]critical payload syntax error[/bold red]" in result.output


def test_k8s_teardown_stack_case_insensitive(process_fake: ProcessFake, env_tree: Path) -> None:
    """Verify teardown-stack normalizes case-insensitive stack names."""
    set_dry_run(True)
    argv = ["teardown-stack", "--stack", "LOGGING", "--k8s-dir", str(env_tree)]
    result = runner.invoke(app, argv)
    assert result.exit_code == 0
    assert "teardown_k8s_stack" in result.output


@pytest.mark.parametrize("follow", [False, True])
def test_k8s_logs_native_streaming_framing_and_literals(
    follow: bool, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """Verify devops k8s logs writes each line via write_stdout without markup or wrapping."""
    cluster.core.answers["read_namespaced_pod_log"] = [
        b"a\nb",
        b"c\n",
        b"literal [/bold] tags\n",
        b"w" * 200 + b"\n",
    ]

    args = ["logs", "pod-1", "-n", "default"]
    if follow:
        args.append("--follow")

    res = runner.invoke(app, args)

    assert (res.exit_code, res.stdout, process_fake.calls) == (
        0,
        f"a\nbc\nliteral [/bold] tags\n{'w' * 200}\n",
        [],
    )


def test_k8s_logs_mid_body_error_raises_without_fallback(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """Verify mid-body error in non-follow mode raises without fallback to kubectl."""
    cluster.core.answers["read_namespaced_pod_log"] = [
        b"head-line\n",
        RuntimeError("mid-stream failure"),
    ]

    res = runner.invoke(app, ["logs", "pod-1", "-n", "default"])

    assert res.exit_code != 0
    assert isinstance(res.exception, RuntimeError)
    assert "head-line\n" in res.stdout
    assert process_fake.calls == []
