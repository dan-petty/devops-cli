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
    Private internal IP: 192.168.1.100
    Test host: test.example.com
    External endpoint: https://auth.vendor-service.io/oauth/token
    Bare domain reference: prod-infra.custom-cloud.io
    File reference: main.py, coverage.xml, dmypy.json, config.yaml (should all be skipped)
    """
    refs = extract_network_references(doc, "docs/deploy.md")
    targets = {r.target: r for r in refs}

    # External targets
    assert "https://api.prod.example-corp.com/v1" in targets
    assert not targets["https://api.prod.example-corp.com/v1"].is_local
    assert targets["https://api.prod.example-corp.com/v1"].scope == "external"

    assert "93.184.216.34" in targets
    assert not targets["93.184.216.34"].is_local

    assert "prod-infra.custom-cloud.io" in targets
    assert not targets["prod-infra.custom-cloud.io"].is_local

    assert "https://auth.vendor-service.io/oauth/token" in targets
    assert not targets["https://auth.vendor-service.io/oauth/token"].is_local

    # Local targets
    assert "192.168.1.100" in targets
    assert targets["192.168.1.100"].is_local
    assert targets["192.168.1.100"].scope == "local"
    assert "Local" in targets["192.168.1.100"].security_status

    assert "test.example.com" in targets
    assert targets["test.example.com"].is_local
    assert targets["test.example.com"].scope == "local"

    # Non-network file references skipped
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
    targets_json = {r.target: r for r in refs_json}
    assert "https://api.external-metrics.io/v1" in targets_json
    assert not targets_json["https://api.external-metrics.io/v1"].is_local

    assert "gateway.production-cloud.net" in targets_json
    assert not targets_json["gateway.production-cloud.net"].is_local

    assert "93.184.216.34" in targets_json
    assert not targets_json["93.184.216.34"].is_local

    assert "10.0.0.5" in targets_json
    assert targets_json["10.0.0.5"].is_local
    assert targets_json["10.0.0.5"].scope == "local"

    yaml_doc = """
    services:
      monitoring:
        url: https://telemetry.custom-service.io/traces
        dns: traces.custom-service.io
        server_ip: 8.8.8.8
    """
    refs_yaml = extract_network_references(yaml_doc, "docker-compose.yml")
    targets_yaml = {r.target: r for r in refs_yaml}
    assert "https://telemetry.custom-service.io/traces" in targets_yaml
    assert "traces.custom-service.io" in targets_yaml
    assert "8.8.8.8" in targets_yaml


def test_extract_network_references_local_and_reserved_spaces() -> None:
    """Test extraction of RFC reserved domains, local TLDs, and private IP spaces."""
    doc = """
    # Local & Internal Services
    Localhost API: http://localhost:8080/v1
    Cluster DNS: jaeger.otel.svc.cluster.local
    Internal node: node1.corp.internal
    Home LAN: server.lan
    Private IP: 192.168.1.1
    Loopback: 127.0.0.1
    Reserved domain: test.example.org
    """
    refs = extract_network_references(doc, "docs/internal.md")
    targets = {r.target: r for r in refs}

    assert "http://localhost:8080/v1" in targets
    assert targets["http://localhost:8080/v1"].is_local

    assert "192.168.1.1" in targets
    assert targets["192.168.1.1"].is_local

    assert "127.0.0.1" in targets
    assert targets["127.0.0.1"].is_local

    assert "test.example.org" in targets
    assert targets["test.example.org"].is_local

    assert "jaeger.otel.svc.cluster.local" in targets
    assert targets["jaeger.otel.svc.cluster.local"].is_local


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


def test_extract_network_references_package_files_and_lockfile_filtering() -> None:
    from devops_cli.security.reference_extractor import (
        is_lockfile_or_ignore_file,
        is_package_repository_asset,
    )

    # Lockfiles should be identified
    assert is_lockfile_or_ignore_file("uv.lock")
    assert is_lockfile_or_ignore_file("poetry.lock")
    assert is_lockfile_or_ignore_file("package-lock.json")
    assert is_lockfile_or_ignore_file("cargo.lock")
    assert is_lockfile_or_ignore_file("yarn.lock")
    assert is_lockfile_or_ignore_file("pnpm-lock.yaml")
    assert is_lockfile_or_ignore_file("composer.lock")
    assert is_lockfile_or_ignore_file("Gemfile.lock")
    assert is_lockfile_or_ignore_file(".gitignore")
    assert not is_lockfile_or_ignore_file("pyproject.toml")
    assert not is_lockfile_or_ignore_file("src/client.py")

    # Lockfile contents should produce 0 network references (covered by dependency checks)
    lock_doc = """
    [[package]]
    name = "foo"
    version = "1.0.0"
    source = { url = "https://files.pythonhosted.org/packages/12/34/foo-1.0.0-py3-none-any.whl" }
    """
    refs_lock = extract_network_references(lock_doc, "uv.lock")
    assert len(refs_lock) == 0

    # Package repository download assets should be recognized
    assert is_package_repository_asset("https://files.pythonhosted.org/packages/foo.whl")
    assert is_package_repository_asset("https://registry.npmjs.org/@scope/pkg/-/pkg-1.0.0.tgz")
    assert is_package_repository_asset(
        "https://static.crates.io/crates/mycrate/mycrate-0.1.0.crate"
    )
    assert is_package_repository_asset(
        "https://repo.maven.apache.org/maven2/org/example/pkg-1.0.jar"
    )
    assert not is_package_repository_asset("https://api.my-vendor-service.io/v1/webhook")

    # In source files, package file download URLs are skipped while legitimate
    # service endpoints are kept
    src_content = """
    pypi_wheel = "https://files.pythonhosted.org/packages/4c/76/pkg-1.0.0.whl"
    npm_tarball = "https://registry.npmjs.org/lib/-/lib-2.0.0.tgz"
    service_api = "https://api.external-monitoring-service.net/v2/events"
    """
    refs_src = extract_network_references(src_content, "src/worker.py")
    targets = {r.target for r in refs_src}
    assert "https://api.external-monitoring-service.net/v2/events" in targets
    assert "https://files.pythonhosted.org/packages/4c/76/pkg-1.0.0.whl" not in targets
    assert "https://registry.npmjs.org/lib/-/lib-2.0.0.tgz" not in targets


def test_extract_network_references_file_extensions_and_code_properties() -> None:
    """Verify source files and telemetry/code properties are not matched as external domains."""
    doc_content = """
    # Architecture & Agent Rules
    See intelligence.py, manager.py, misc.py, common.py, helpers.py.
    Also check postcreate.sh, architect.md, devsecops.md, vpc.tf, lib.rs, git-daemon.pid.
    Span attributes: service.name, ci.step.security, host.name, process.pid, concurrency.group.
    Legitimate domain: api.datadoghq.com and auth.auth0.com.
    """
    refs = extract_network_references(doc_content, "docs/architecture.md")
    targets = {r.target for r in refs}

    # Legitimate external domains
    assert "api.datadoghq.com" in targets
    assert "auth.auth0.com" in targets

    # Source files should NOT be extracted as domains
    assert "intelligence.py" not in targets
    assert "manager.py" not in targets
    assert "postcreate.sh" not in targets
    assert "architect.md" not in targets
    assert "devsecops.md" not in targets
    assert "vpc.tf" not in targets
    assert "lib.rs" not in targets
    assert "git-daemon.pid" not in targets

    # Span and code attribute properties should NOT be extracted as domains
    assert "service.name" not in targets
    assert "ci.step.security" not in targets
    assert "host.name" not in targets
    assert "process.pid" not in targets
    assert "concurrency.group" not in targets
