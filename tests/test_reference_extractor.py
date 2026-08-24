"""Unit tests for dependency and network reference extractors."""

from __future__ import annotations

from devops_cli.security.reference_extractor import (
    extract_dependencies_from_text,
    extract_network_references,
    is_public_ip,
)


def test_is_public_ip() -> None:
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("1.1.1.1") is True
    assert is_public_ip("127.0.0.1") is False
    assert is_public_ip("192.168.1.1") is False
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip("172.16.0.1") is False
    assert is_public_ip("invalid-ip") is False


def test_extract_dependencies_requirements_txt() -> None:
    content = """
    # Comments
    pydantic>=2.10.0
    httpx==0.28.1
    typer~=0.15.0
    pytest
    """
    deps = extract_dependencies_from_text(content, "requirements.txt")
    assert len(deps) == 4
    names = {d.name: d.version_range for d in deps}
    assert names["pydantic"] == ">=2.10.0"
    assert names["httpx"] == "==0.28.1"
    assert names["typer"] == "~=0.15.0"
    assert names["pytest"] == "*"


def test_extract_dependencies_package_json() -> None:
    content = """{
        "dependencies": {
            "react": "^18.2.0",
            "next": "14.1.0"
        },
        "devDependencies": {
            "typescript": "^5.0.0"
        }
    }"""
    deps = extract_dependencies_from_text(content, "package.json")
    assert len(deps) == 3
    assert all(d.ecosystem == "npm" for d in deps)


def test_extract_dependencies_cargo_and_go() -> None:
    cargo_content = """[dependencies]
    serde = "1.0"
    tokio = "1.35"
    """
    cargo_deps = extract_dependencies_from_text(cargo_content, "Cargo.toml")
    assert len(cargo_deps) == 2
    assert cargo_deps[0].ecosystem == "crates.io"

    go_content = """module example.com/foo
    go 1.22
    require (
        github.com/gin-gonic/gin v1.9.1
    )
    """
    go_deps = extract_dependencies_from_text(go_content, "go.mod")
    assert len(go_deps) == 1
    assert go_deps[0].ecosystem == "Go"


def test_extract_network_references() -> None:
    doc = """
    # Deployment Guide
    Access the cluster at https://api.prod.example-corp.com/v1
    Public ingress IP: 93.184.216.34
    Private internal IP: 192.168.1.100 (should be skipped)
    Test host: test.example.com (should be skipped)
    External endpoint: https://auth.vendor-service.io/oauth/token
    Bare domain reference: prod-infra.custom-cloud.io
    File reference: main.py, coverage.xml, dmypy.json, config.yaml (should all be skipped)
    """
    refs = extract_network_references(doc, "docs/deploy.md")
    targets = {r.target for r in refs}
    assert "https://api.prod.example-corp.com/v1" in targets
    assert "93.184.216.34" in targets
    assert "prod-infra.custom-cloud.io" in targets
    assert "192.168.1.100" not in targets
    assert "https://auth.vendor-service.io/oauth/token" in targets
    assert "main.py" not in targets
    assert "coverage.xml" not in targets
    assert "dmypy.json" not in targets
    assert "config.yaml" not in targets


def test_extract_network_references_gitignore_filtering() -> None:
    gitignore_content = """
    .venv/
    dmypy.json
    coverage.xml
    thumbs.db
    config.example.yaml
    config.yaml
    *.pyc
    *.log
    """
    refs = extract_network_references(gitignore_content, ".gitignore")
    assert len(refs) == 0


def test_extract_network_references_python_code_token_filtering() -> None:
    """Ensure Python function calls, method chains, imports, and variables are not matched."""
    python_code = """
    import logging
    from unittest.mock import MagicMock
    import pytest
    import typer

    logger = logging.getLogger(__name__)

    class Client:
        def __init__(self):
            self.settings = {"url": "https://api.example-service.com"}
            self.sdk = MagicMock()
            self.authenticated = False

        def get_data(self):
            logger.debug("fetching")
            res = self.sdk.get.sites()
            data = res.get("items")
            endpoint = "https://custom-cloud.io/v1/metrics"
            domain_literal = "metrics.internal-monitoring.net"
            return data

    def test_func():
        with pytest.raises(ValueError):
            runner.invoke(app, ["serve"])
    """
    refs = extract_network_references(python_code, "src/service/client.py")
    targets = {r.target for r in refs}

    # Should find legitimate URLs and quoted string domain literals
    assert "https://api.example-service.com" in targets
    assert "https://custom-cloud.io/v1/metrics" in targets
    assert "metrics.internal-monitoring.net" in targets

    # Must NOT match Python code tokens, functions, methods, or attributes
    assert "logging.getlogger" not in targets
    assert "self.settings" not in targets
    assert "self.sdk" not in targets
    assert "self.authenticated" not in targets
    assert "logger.debug" not in targets
    assert "self.sdk.get.sites" not in targets
    assert "res.get" not in targets
    assert "pytest.raises" not in targets
    assert "runner.invoke" not in targets
    assert "unittest.mock" not in targets


def test_extract_network_references_toml_table_filtering() -> None:
    """Ensure TOML table headers like tool.ruff, tool.pytest are not treated as domains."""
    toml_content = """
    [project]
    name = "demo-pkg"
    homepage = "https://custom-vendor.org"
    server_domain = "api.custom-vendor.org"

    [tool.ruff]
    line-length = 100

    [tool.ruff.lint]
    select = ["E", "F"]

    [tool.pytest.ini_options]
    testpaths = ["tests"]

    [tool.mypy]
    strict = true
    """
    refs = extract_network_references(toml_content, "pyproject.toml")
    targets = {r.target for r in refs}

    assert "https://custom-vendor.org" in targets
    assert "api.custom-vendor.org" in targets
    assert "tool.ruff" not in targets
    assert "tool.ruff.lint" not in targets
    assert "tool.pytest" not in targets
    assert "tool.mypy" not in targets


def test_extract_network_references_code_false_positives_filtering() -> None:
    """Ensure programming code, git config keys, pip-tools files, and mock paths are not domains."""
    workflow_yaml = """
    name: Release
    jobs:
      release:
        runs-on: ubuntu-latest
        steps:
          - name: Setup git
            run: |
              git config user.name "github-actions"
              git config user.email "action@github.com"
          - name: Login to GHCR
            run: |
              echo ${{ secrets.TOKEN }} | docker login ghcr.io -u ${{ github.actor }}
    """
    refs_yaml = extract_network_references(workflow_yaml, ".github/workflows/release.yml")
    targets_yaml = {r.target for r in refs_yaml}
    assert "user.email" not in targets_yaml
    assert "user.name" not in targets_yaml
    assert "ghcr.io" in targets_yaml

    py_content = """
    # Mocking patch
    @patch("devops_cli.commands.workspace.subprocess.run")
    @patch("devops_cli.ai.agents.pipeline.multiagentpipeline.run")
    def test_run():
        m = re.match(r"^test", "test")
        val = m.group(0)
        from devops_cli.commands.ai import app
        self.host = "localhost"
        domain = "prod-infra.custom-cloud.io"
        file_ref = "requirements.in"
    """
    refs_py = extract_network_references(py_content, "tests/test_mock.py")
    targets_py = {r.target for r in refs_py}
    assert "devops_cli.commands.workspace.subprocess.run" not in targets_py
    assert "devops_cli.ai.agents.pipeline.multiagentpipeline.run" not in targets_py
    assert "m.group" not in targets_py
    assert "commands.ai" not in targets_py
    assert "self.host" not in targets_py
    assert "requirements.in" not in targets_py
    assert "prod-infra.custom-cloud.io" in targets_py


def test_extract_network_references_tf_and_python_imports() -> None:
    """Ensure Terraform attributes and Python imports are not extracted as domains."""
    tf_content = """
    resource "aws_route" "r" {
      route_table_id = aws_route_table.public.id
      nat_gateway_id = aws_nat_gateway.nat.id
      gateway_id     = aws_internet_gateway.igw.id
    }
    output "cluster_name" {
      value = aws_eks_cluster.eks.name
    }
    """
    refs_tf = extract_network_references(tf_content, "tf/aws/main.tf")
    targets_tf = {r.target for r in refs_tf}
    assert "nat.id" not in targets_tf
    assert "igw.id" not in targets_tf
    assert "public.id" not in targets_tf
    assert "eks.name" not in targets_tf

    py_imports = """
    from collections.abc import Sequence
    from devops_cli.models.ai import FileAnalysisMeta
    import httpx.client.post
    """
    refs_py = extract_network_references(py_imports, "src/devops_cli/foo.py")
    targets_py = {r.target for r in refs_py}
    assert "collections.abc" not in targets_py
    assert "models.ai" not in targets_py
    assert "httpx.client.post" not in targets_py


def test_extract_dependencies_pep621_and_extras() -> None:
    """Test standard PEP 621 pyproject dependencies, optional groups, and PEP 508 extras."""
    req_txt = """
    # Comments and blank lines
    pydantic[email]>=2.10.0
    uvicorn[standard]==0.30.0; python_version >= '3.10'
    """
    deps_req = extract_dependencies_from_text(req_txt, "requirements.txt")
    assert len(deps_req) == 2
    assert deps_req[0].name == "pydantic"
    assert deps_req[0].version_range == ">=2.10.0"

    pyproject_toml = """
    [project]
    name = "my-service"
    dependencies = [
        "fastapi>=0.110.0",
        "httpx~=0.28.0",
    ]

    [project.optional-dependencies]
    test = [
        "pytest>=8.0.0",
        "pytest-asyncio",
    ]

    [dependency-groups]
    dev = [
        "ruff>=0.9.0",
        "mypy>=1.14.0",
    ]
    """
    deps_toml = extract_dependencies_from_text(pyproject_toml, "pyproject.toml")
    names = {d.name: d.version_range for d in deps_toml}
    assert "fastapi" in names
    assert names["fastapi"] == ">=0.110.0"
    assert "pytest" in names
    assert names["pytest"] == ">=8.0.0"
    assert "pytest-asyncio" in names
    assert names["pytest-asyncio"] == "*"
    assert "ruff" in names
    assert names["ruff"] == ">=0.9.0"


def test_extract_network_references_json_and_yaml_scalars() -> None:
    """Test extracting network references from structured JSON and YAML configs."""
    json_doc = """
    {
        "api_endpoint": "https://api.external-metrics.io/v1",
        "primary_host": "gateway.production-cloud.net",
        "internal_ip": "10.0.0.5",
        "public_ip": "93.184.216.34"
    }
    """
    refs_json = extract_network_references(json_doc, "config/settings.json")
    targets_json = {r.target for r in refs_json}
    assert "https://api.external-metrics.io/v1" in targets_json
    assert "gateway.production-cloud.net" in targets_json
    assert "93.184.216.34" in targets_json
    assert "10.0.0.5" not in targets_json

    yaml_doc = """
    services:
      monitoring:
        url: https://telemetry.custom-service.io/traces
        dns: traces.custom-service.io
        server_ip: 8.8.8.8
    """
    refs_yaml = extract_network_references(yaml_doc, "docker-compose.yml")
    targets_yaml = {r.target for r in refs_yaml}
    assert "https://telemetry.custom-service.io/traces" in targets_yaml
    assert "traces.custom-service.io" in targets_yaml
    assert "8.8.8.8" in targets_yaml


def test_extract_network_references_function_calls_and_workspace_files() -> None:
    """Ensure function calls and workspace files are not extracted as external domains."""
    content = """
    # Programmatic function calls
    result = not.a.domain.com("arg1", 42)
    response = service.client.call(endpoint="test")
    val = helper.utils.format(data)

    # Workspace filenames and components
    file1 = "auth.py"
    file2 = "server.py"
    file3 = "logging.py"
    file4 = "test_reference_extractor.py"
    file5 = "review.py"

    # Legitimate external domain and URL
    legit_domain = "metrics.telemetry-cloud.io"
    legit_url = "https://dashboard.production-network.net/status"
    """
    refs = extract_network_references(content, "src/devops_cli/example.py")
    targets = {r.target for r in refs}

    # Function calls must NOT be matched as domains
    assert "not.a.domain.com" not in targets
    assert "service.client.call" not in targets
    assert "helper.utils.format" not in targets

    # Workspace files must NOT be matched as external domains
    assert "auth.py" not in targets
    assert "server.py" not in targets
    assert "logging.py" not in targets
    assert "test_reference_extractor.py" not in targets
    assert "review.py" not in targets

    # Legitimate external references must be extracted
    assert "metrics.telemetry-cloud.io" in targets
    assert "https://dashboard.production-network.net/status" in targets


def test_dependency_and_network_reference_canonical_location_formatting() -> None:
    from devops_cli.models.vulnerability import DependencySpec, NetworkReference

    dep_with_line = DependencySpec(
        name="pydantic",
        version_range=">=2.10.0",
        source_file="pyproject.toml",
        line_number=42,
    )
    assert dep_with_line.location == "pyproject.toml:42"

    dep_no_line = DependencySpec(
        name="pytest",
        source_file="requirements.txt",
    )
    assert dep_no_line.location == "requirements.txt:1"

    net_with_line = NetworkReference(
        target="api.example.com",
        source_file="src/client.py",
        line_number=88,
    )
    assert net_with_line.location == "src/client.py:88"
