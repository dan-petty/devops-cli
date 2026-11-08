"""Unit and CLI tests for devops tls subcommands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.tls import app
from devops_cli.crypto.tls_certificates import generate_ca_certificate, generate_server_certificate
from tests.support.fakes.process import ProcessAnswer, ProcessFake

runner = CliRunner()


def test_tls_ca_command_live(tmp_path: Path) -> None:
    """devops tls ca creates a root CA in target directory."""
    result = runner.invoke(
        app, ["ca", "--output-dir", str(tmp_path), "--common-name", "CLI Root CA"]
    )
    assert result.exit_code == 0
    assert "Generated Root Certificate Authority" in result.output
    assert (tmp_path / "ca.crt").exists()
    assert (tmp_path / "ca.key").exists()


def test_tls_cert_command_live(tmp_path: Path) -> None:
    """devops tls cert generates signed server certificate with SANs."""
    # First create CA
    generate_ca_certificate(output_dir=tmp_path)

    result = runner.invoke(
        app,
        [
            "cert",
            "--output-dir",
            str(tmp_path),
            "--common-name",
            "example.com",
            "--san",
            "example.com",
            "--san",
            "127.0.0.1",
        ],
    )
    assert result.exit_code == 0
    assert "Generated TLS Certificate" in result.output
    assert (tmp_path / "tls.crt").exists()
    assert (tmp_path / "tls.key").exists()
    assert (tmp_path / "fullchain.crt").exists()


def test_tls_homelab_command(tmp_path: Path) -> None:
    """devops tls homelab generates full certificate bundle."""
    result = runner.invoke(app, ["homelab", "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Homelab TLS Certificate Bundle Generated" in result.output
    assert (tmp_path / "ca.crt").exists()
    assert (tmp_path / "tls.crt").exists()
    assert (tmp_path / "tls.key").exists()


def test_tls_inspect_and_verify_command(tmp_path: Path) -> None:
    """devops tls inspect and devops tls verify work on generated certificates."""
    ca_cert, ca_key = generate_ca_certificate(output_dir=tmp_path)
    srv_cert, _, _ = generate_server_certificate(
        common_name="example.com",
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=tmp_path,
    )

    # Test inspect
    inspect_res = runner.invoke(app, ["inspect", str(srv_cert)])
    assert inspect_res.exit_code == 0
    assert "Certificate Inspection" in inspect_res.output
    assert "example.com" in inspect_res.output

    # Test verify
    verify_res = runner.invoke(app, ["verify", str(srv_cert), "--ca-cert", str(ca_cert)])
    assert verify_res.exit_code == 0
    assert "Verified:" in verify_res.output


def test_tls_ca_cert_and_inspect_commands_read_each_others_files(tmp_path: Path, cli: Any) -> None:
    """Verify tls ca, cert, and inspect commands chain through the files they write."""
    ca_cert = tmp_path / "ca.crt"
    ca_key = tmp_path / "ca.key"
    srv_cert = tmp_path / "tls.crt"

    res_ca = cli("tls", "ca", "--output-dir", str(tmp_path))
    assert res_ca.exit_code == 0
    assert (ca_cert.exists(), ca_key.exists()) == (True, True)

    res_cert = cli(
        "tls",
        "cert",
        "--common-name",
        "example.com",
        "--ca-cert",
        str(ca_cert),
        "--ca-key",
        str(ca_key),
        "--output-dir",
        str(tmp_path),
    )
    assert res_cert.exit_code == 0
    assert srv_cert.exists()

    res_insp = cli("tls", "inspect", str(srv_cert))
    assert res_insp.exit_code == 0
    assert "example.com" in res_insp.output


def test_tls_verification_failures(tmp_path: Path, cli: Any) -> None:
    """Verify the error branches of tls verify."""
    # Missing cert
    res_no_cert = cli("tls", "verify", "/nonexistent/cert.crt", "--ca-cert", "/nonexistent/ca.crt")
    assert res_no_cert.exit_code == 1

    # Missing CA
    cert_file = tmp_path / "valid.crt"
    cert_file.touch()
    res_no_ca = cli("tls", "verify", str(cert_file), "--ca-cert", "/nonexistent/ca.crt")
    assert res_no_ca.exit_code == 1

    # Failed verification: the certificate came from another authority
    ca_cert, ca_key = generate_ca_certificate(output_dir=tmp_path / "issuer")
    other_ca_cert, _other_key = generate_ca_certificate(output_dir=tmp_path / "other")
    srv_cert, _, _ = generate_server_certificate(
        common_name="example.com",
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=tmp_path / "issuer",
    )
    res_fail = cli("tls", "verify", str(srv_cert), "--ca-cert", str(other_ca_cert))
    assert res_fail.exit_code == 1


def test_tls_enable_k8s_execution(tmp_path: Path, cli: Any, process_fake: ProcessFake) -> None:
    """Verify devops tls enable-k8s non-dry-run subprocess execution."""
    cert_file = tmp_path / "tls.crt"
    key_file = tmp_path / "tls.key"
    cert_file.touch()
    key_file.touch()

    # Both namespace exists & secret creates successfully
    res_ok = cli("tls", "enable-k8s", "--tls-dir", str(tmp_path), "--namespace", "default")
    assert res_ok.exit_code == 0
    assert "Created" in res_ok.output

    # Create fails
    process_fake.answer(
        lambda call: "create" in call.argv and "secret" in call.argv,
        ProcessAnswer(returncode=1, stderr="PermissionDenied"),
    )
    res_fail = cli("tls", "enable-k8s", "--tls-dir", str(tmp_path), "--namespace", "default")
    assert res_fail.exit_code == 0
    assert "Failed" in res_fail.output


def test_tls_enable_k8s_leaves_the_live_secret_when_the_new_one_is_rejected(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """`devops tls enable-k8s` never deletes a secret it cannot replace (#961).

    It deleted each namespace's secret and then created the new one, so a certificate and
    key kubectl rejects left the namespace with no secret at all.
    """
    (tmp_path / "tls.crt").write_text("certificate", encoding="utf-8")
    (tmp_path / "tls.key").write_text("rotated key", encoding="utf-8")
    process_fake.answer(
        lambda call: {"create", "secret", "tls"} <= set(call.argv),
        ProcessAnswer(returncode=1, stderr="tls: private key does not match"),
    )

    result = cli("tls", "enable-k8s", "--tls-dir", str(tmp_path), "--namespace", "web")

    changes = [call.argv for call in process_fake.calls if {"delete", "apply"} & set(call.argv)]
    assert (result.exit_code, changes, "private key does not match" in result.output) == (
        0,
        [],
        True,
    )


def test_tls_enable_k8s_applies_the_rendered_secret_over_the_live_one(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """`devops tls enable-k8s` renders each secret client-side, then applies it (#961)."""
    cert_path, key_path = tmp_path / "tls.crt", tmp_path / "tls.key"
    cert_path.write_text("certificate", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")
    process_fake.answer(
        lambda call: "--dry-run=client" in call.argv, ProcessAnswer(stdout="kind: Secret\n")
    )

    result = cli(
        "tls",
        "enable-k8s",
        "--tls-dir",
        str(tmp_path),
        "--namespace",
        "web",
        "--secret-name",
        "web-tls",
    )

    assert (
        result.exit_code,
        [(list(call.argv), call.stdin) for call in process_fake.calls[1:]],
        "Created" in result.output,
    ) == (
        0,
        [
            (
                ["kubectl", "create", "secret", "tls", "web-tls"]
                + [f"--cert={cert_path}", f"--key={key_path}", "-n", "web"]
                + ["--dry-run=client", "-o", "yaml"],
                None,
            ),
            (["kubectl", "apply", "-f", "-", "-n", "web"], "kind: Secret\n"),
        ],
        True,
    )


# =============================================================================
# Dry runs (#2258)
# =============================================================================


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


def _squash(output: str) -> str:
    """The output with each run of white space as one space."""
    return " ".join(output.split())


def test_tls_dry_run_classes() -> None:
    """Each tls command carries the dry-run class of what it reaches."""
    from devops_cli.commands import tls
    from devops_cli.dry_run.decorator import get_dry_run_class

    for callback in (
        tls.cmd_ca,
        tls.generate_cert_cmd,
        tls.generate_homelab_cmd,
        tls.inspect_cmd,
        tls.verify_cmd,
    ):
        assert get_dry_run_class(callback) == "no-external-request"
    assert get_dry_run_class(tls.enable_k8s_cmd) == "request-plan"


def test_tls_inspect_and_verify_run_under_the_dry_run_flag(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """A command that reads a local certificate runs normally under `devops --dry-run`."""
    ca_cert, ca_key = generate_ca_certificate(output_dir=tmp_path)
    srv_cert, _srv_key, _chain = generate_server_certificate(
        common_name="example.com",
        sans=["example.com"],
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
        output_dir=tmp_path,
    )

    inspected = cli(["--dry-run", "tls", "inspect", str(srv_cert)])
    verified = cli(["--dry-run", "tls", "verify", str(srv_cert), "--ca-cert", str(ca_cert)])

    assert inspected.exit_code == 0, inspected.output
    assert "Certificate Inspection" in inspected.output
    assert verified.exit_code == 0, verified.output
    assert "Verified:" in verified.output
    assert process_fake.calls == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("ca", "Would write the CA certificate {dir}/ca.crt and its key {dir}/ca.key"),
        ("cert", "Would write the certificate {dir}/tls.crt for"),
        ("homelab", "Would write the homelab bundle"),
    ],
)
@pytest.mark.parametrize("flag_first", [True, False])
def test_tls_writers_preview_under_dry_run_and_write_nothing(
    tmp_path: Path, cli: Any, command: str, expected: str, flag_first: bool
) -> None:
    """A dry run says which files it would write, and writes none."""
    out_dir = tmp_path / "out"
    argv = ["tls", command, "--output-dir", str(out_dir)]
    argv = ["--dry-run", *argv] if flag_first else [*argv, "--dry-run"]

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert expected.format(dir=out_dir) in _squash(result.output)
    assert not out_dir.exists()


def _tls_dir(tmp_path: Path) -> Path:
    tls_dir = tmp_path / "tls"
    tls_dir.mkdir()
    (tls_dir / "tls.crt").write_text("certificate", encoding="utf-8")
    (tls_dir / "tls.key").write_text("key", encoding="utf-8")
    return tls_dir


@pytest.mark.parametrize("flag_first", [True, False])
def test_tls_enable_k8s_dry_run_lists_the_kubectl_requests(
    tmp_path: Path, cli: Any, process_fake: ProcessFake, flag_first: bool
) -> None:
    """A dry run starts no kubectl and lists the four requests of each namespace in order."""
    tls_dir = _tls_dir(tmp_path)
    argv = ["tls", "enable-k8s", "--tls-dir", str(tls_dir), "-n", "web", "-n", "db"]
    argv = ["--dry-run", *argv] if flag_first else [*argv, "--dry-run"]

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    cert, key = tls_dir / "tls.crt", tls_dir / "tls.key"
    expected: list[str] = []
    for ns in ("web", "db"):
        expected += [
            f"kubectl get namespace {ns}",
            f"kubectl create namespace {ns}  [only if the namespace does not exist]",
            f"kubectl create secret tls homelab-tls --cert={cert} --key={key} -n {ns} "
            "--dry-run=client -o yaml",
            f"kubectl apply -f - -n {ns}  [only if the secret renders]",
        ]
    assert _plan_lines(result.output) == expected
    assert "<output of the previous request>" in result.output
    assert "homelab bundle" not in result.output


def test_tls_enable_k8s_dry_run_with_a_context_and_no_bundle(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """Each request names the context, and a missing bundle is a note, not a write."""
    tls_dir = tmp_path / "empty"

    result = cli(
        ["tls", "enable-k8s", "--tls-dir", str(tls_dir), "-n", "web", "-c", "example", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert all(
        line.split("  [")[0].endswith("--context example") for line in _plan_lines(result.output)
    )
    assert f"the run writes the homelab bundle to {tls_dir}" in _squash(result.output)
    assert not tls_dir.exists()


def test_tls_enable_k8s_runs_the_requests_of_its_plan(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """The real run starts the commands of the plan, in the same order, and applies the
    rendered secret."""
    tls_dir = _tls_dir(tmp_path)
    argv = ["tls", "enable-k8s", "--tls-dir", str(tls_dir), "-n", "web"]
    planned = [line.split("  [")[0] for line in _plan_lines(cli([*argv, "--dry-run"]).output)]
    process_fake.answer(["kubectl", "get", "namespace"], ProcessAnswer(returncode=1))
    process_fake.answer(
        lambda call: "--dry-run=client" in call.argv, ProcessAnswer(stdout="kind: Secret\n")
    )

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert [" ".join(call.argv) for call in process_fake.calls] == planned
    assert process_fake.calls[-1].stdin == "kind: Secret\n"
