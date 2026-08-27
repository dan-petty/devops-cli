"""Unit tests for dependency and network reference extractors."""

from __future__ import annotations

from pathlib import Path

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
    target_api = targets.get("https://api.prod.example-corp.com/v1")
    assert target_api is not None
    assert not target_api.is_local
    assert target_api.scope == "external"

    target_ip = targets.get("93.184.216.34")
    assert target_ip is not None
    assert not target_ip.is_local

    target_infra = targets.get("prod-infra.custom-cloud.io")
    assert target_infra is not None
    assert not target_infra.is_local

    target_auth = targets.get("https://auth.vendor-service.io/oauth/token")
    assert target_auth is not None
    assert not target_auth.is_local

    # Local targets
    target_local_ip = targets.get("192.168.1.100")
    assert target_local_ip is not None
    assert target_local_ip.is_local
    assert target_local_ip.scope == "local"
    assert "Local" in target_local_ip.security_status

    target_local_domain = targets.get("test.example.com")
    assert target_local_domain is not None
    assert target_local_domain.is_local
    assert target_local_domain.scope == "local"

    # Non-network file references skipped
    assert targets.get("main.py") is None
    assert targets.get("coverage.xml") is None
    assert targets.get("dmypy.json") is None
    assert targets.get("config.yaml") is None


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
    assert any(t == "https://api.example-service.com" for t in targets)
    assert any(t == "https://custom-cloud.io/v1/metrics" for t in targets)
    assert any(t == "metrics.internal-monitoring.net" for t in targets)

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

    assert any(t == "https://custom-vendor.org" for t in targets)
    assert any(t == "api.custom-vendor.org" for t in targets)
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
    assert any(t == "ghcr.io" for t in targets_yaml)

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
    assert any(t == "prod-infra.custom-cloud.io" for t in targets_py)


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
    t_api = targets_json.get("https://api.external-metrics.io/v1")
    assert t_api is not None
    assert not t_api.is_local

    t_host = targets_json.get("gateway.production-cloud.net")
    assert t_host is not None
    assert not t_host.is_local

    t_pub_ip = targets_json.get("93.184.216.34")
    assert t_pub_ip is not None
    assert not t_pub_ip.is_local

    t_int_ip = targets_json.get("10.0.0.5")
    assert t_int_ip is not None
    assert t_int_ip.is_local
    assert t_int_ip.scope == "local"

    yaml_doc = """
    services:
      monitoring:
        url: https://telemetry.custom-service.io/traces
        dns: traces.custom-service.io
        server_ip: 8.8.8.8
    """
    refs_yaml = extract_network_references(yaml_doc, "docker-compose.yml")
    targets_yaml = {r.target: r for r in refs_yaml}
    assert targets_yaml.get("https://telemetry.custom-service.io/traces") is not None
    assert targets_yaml.get("traces.custom-service.io") is not None
    assert targets_yaml.get("8.8.8.8") is not None


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

    t_local_api = targets.get("http://localhost:8080/v1")
    assert t_local_api is not None
    assert t_local_api.is_local

    t_p_ip = targets.get("192.168.1.1")
    assert t_p_ip is not None
    assert t_p_ip.is_local

    t_loop = targets.get("127.0.0.1")
    assert t_loop is not None
    assert t_loop.is_local

    t_res_dom = targets.get("test.example.org")
    assert t_res_dom is not None
    assert t_res_dom.is_local

    t_svc_dns = targets.get("jaeger.otel.svc.cluster.local")
    assert t_svc_dns is not None
    assert t_svc_dns.is_local


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
    assert any(t == "metrics.telemetry-cloud.io" for t in targets)
    assert any(t == "https://dashboard.production-network.net/status" for t in targets)


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
    assert any(t == "https://api.external-monitoring-service.net/v2/events" for t in targets)
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
    assert any(t == "api.datadoghq.com" for t in targets)
    assert any(t == "auth.auth0.com" for t in targets)

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


def test_is_file_reference_and_code_config_reference(tmp_path: Path) -> None:
    """Verify is_file_reference and is_code_or_config_reference detection."""
    from devops_cli.security.reference_extractor import (
        is_code_or_config_reference,
        is_file_reference,
    )

    # Empty target
    assert not is_file_reference("")

    # Relative paths and extensions
    assert is_file_reference("src/devops_cli/main.py")
    assert is_file_reference("config.yaml")
    assert is_file_reference("./script.sh")
    assert is_file_reference("schema.sql")
    assert is_file_reference(".env.local")

    # Code / config references
    assert is_code_or_config_reference("foo.bar()")
    assert is_code_or_config_reference("my_func_call")
    assert is_code_or_config_reference("-invalid-hostname-")
    assert is_code_or_config_reference("self.client")
    assert is_code_or_config_reference("os.path")
    assert is_code_or_config_reference("m.group")
    assert is_code_or_config_reference("x.y")
    assert not is_code_or_config_reference("api.example.com")


def test_extract_dependencies_various_ecosystems() -> None:
    """Verify requirements-dev.txt, requirements.in, invalid json/toml error fallbacks, and unsupported manifests."""
    # requirements-dev.txt
    req_dev = "ruff>=0.9.0\nmypy>=1.14.0\n"
    dev_deps = extract_dependencies_from_text(req_dev, "requirements-dev.txt")
    assert len(dev_deps) == 2

    # requirements.in
    req_in = "fastapi\nuvicorn\n"
    in_deps = extract_dependencies_from_text(req_in, "requirements.in")
    assert len(in_deps) == 2

    # Invalid package.json
    assert extract_dependencies_from_text("{invalid json", "package.json") == []

    # Invalid Cargo.toml
    assert extract_dependencies_from_text("invalid [toml", "Cargo.toml") == []

    # Unsupported manifest
    assert extract_dependencies_from_text("some content", "unknown.manifest") == []


def test_is_network_domain_and_token_parsing() -> None:
    """Verify is_network_domain edge cases, reserved domains, and token string parsing."""
    from devops_cli.security.reference_extractor import (
        _parse_python_token_string,
        is_network_domain,
    )

    # 1. is_network_domain
    assert is_network_domain("api.datadoghq.com") is True
    assert is_network_domain("auth0.com") is True
    assert not is_network_domain("api.prod.example.com")  # reserved RFC domain
    assert not is_network_domain("")
    assert not is_network_domain("no-dots")
    assert not is_network_domain("domain.com/with/path")
    assert not is_network_domain("192.168.1.1")
    assert not is_network_domain("10.0.0.1")
    assert not is_network_domain("func_call(arg)")
    assert not is_network_domain("test.example")  # reserved RFC domain
    assert not is_network_domain("localhost")

    # 2. _parse_python_token_string
    assert _parse_python_token_string('"hello"') == "hello"
    assert _parse_python_token_string("'world'") == "world"
    assert _parse_python_token_string('"""multi"""') == "multi"
    assert _parse_python_token_string("raw_identifier") == "raw_identifier"


def test_reference_extractor_language_parsers() -> None:
    """Verify literal and comment extraction for Python, HCL, and YAML scalars."""
    from devops_cli.security.reference_extractor import (
        _clean_yaml_scalar,
        _extract_hcl_literals_and_comments,
        _extract_python_literals_and_comments,
    )

    # 1. Python literals & comments
    py_src = """
    # Security header
    API_URL = "https://api.segment.io/v1"
    # End of file
    """
    py_lits = _extract_python_literals_and_comments(py_src)
    assert any(lit[0] == "https://api.segment.io/v1" for lit in py_lits)
    assert any("Security header" in lit[0] for lit in py_lits)

    # 2. HCL literals & comments
    hcl_src = """
    # Terraform VPC config
    resource "aws_security_group" "sg" {
        cidr_blocks = ["198.51.100.0/24"] // public CIDR
        /* Multi-line
           comment */
    }
    """
    hcl_lits = _extract_hcl_literals_and_comments(hcl_src)
    assert any("198.51.100.0/24" in lit[0] for lit in hcl_lits)
    assert any("Terraform VPC config" in lit[0] for lit in hcl_lits)

    # 3. YAML scalar cleaner
    cleaned = _clean_yaml_scalar(
        "curl -H 'Authorization: ${{ secrets.TOKEN }}' https://api.site.com"
    )
    assert "${{" not in cleaned
    assert any(token == "https://api.site.com" for token in cleaned.split())


def test_reference_extractor_extended_network_and_lockfiles() -> None:
    """Verify lockfile detection, package asset filtering, and structured string extractions."""
    from devops_cli.security.reference_extractor import (
        _extract_ip_reference,
        _extract_json_strings,
        _extract_toml_strings,
        _extract_url_reference,
        _extract_yaml_strings,
        is_local_or_reserved_domain,
        is_lockfile_or_ignore_file,
        is_package_repository_asset,
    )

    # 1. Lockfiles and ignore files
    assert is_lockfile_or_ignore_file("poetry.lock") is True
    assert is_lockfile_or_ignore_file("pnpm-lock.yaml") is True
    assert is_lockfile_or_ignore_file(".dockerignore") is True
    assert is_lockfile_or_ignore_file("main.py") is False

    # 2. Package repository assets
    assert (
        is_package_repository_asset("https://registry.npmjs.org/express/-/express-4.18.2.tgz")
        is True
    )
    assert (
        is_package_repository_asset("https://crates.io/api/v1/crates/tokio/1.0.0/download") is True
    )
    assert is_package_repository_asset("https://app.datadoghq.com/api/v1/query") is False

    # 3. Local/reserved domain checks
    assert is_local_or_reserved_domain("service.cluster.local") is True
    assert is_local_or_reserved_domain("database.svc") is True
    assert is_local_or_reserved_domain("router.lan") is True
    assert is_local_or_reserved_domain("node.internal") is True
    assert is_local_or_reserved_domain("api.datadoghq.com") is False

    # 4. URL and IP reference extractors
    url_local = _extract_url_reference(
        "http://192.168.1.100:8080/api", "config.py", 5, include_local=True
    )
    assert url_local is not None and url_local.is_local is True

    url_local_skip = _extract_url_reference(
        "http://192.168.1.100:8080/api", "config.py", 5, include_local=False
    )
    assert url_local_skip is None

    ip_pub = _extract_ip_reference("8.8.8.8", "config.py", 12, include_local=False)
    assert ip_pub is not None and ip_pub.is_local is False

    # 5. Structured string extraction
    json_strs = _extract_json_strings('{"server": "https://api.example.com", "port": 8080}')
    assert any(s[0] == "https://api.example.com" for s in json_strs)

    toml_strs = _extract_toml_strings('[tool.poetry]\nname = "my-tool"\n')
    assert any("my-tool" in s[0] for s in toml_strs)

    yaml_strs = _extract_yaml_strings("services:\n  web:\n    image: nginx:alpine\n")
    assert any("nginx:alpine" in s[0] for s in yaml_strs)


def test_extract_network_references_from_various_files() -> None:
    """Verify network reference extraction across Go, Rust, and Dockerfile contents."""
    from devops_cli.security.reference_extractor import extract_network_references

    go_content = 'package main\nconst ApiUrl = "https://api.datadoghq.com/api/v1/query"\n'
    go_refs = extract_network_references(go_content, "main.go", include_local=True)
    assert any(r.target == "https://api.datadoghq.com/api/v1/query" for r in go_refs)

    rs_content = 'pub const ENDPOINT: &str = "https://api.auth0.com/oauth/token";\n'
    rs_refs = extract_network_references(rs_content, "lib.rs", include_local=True)
    assert any(r.target == "https://api.auth0.com/oauth/token" for r in rs_refs)

    docker_content = (
        "FROM alpine:3.19\nRUN curl -fsSL https://app.datadoghq.com/agent -o agent.sh\n"
    )
    docker_refs = extract_network_references(docker_content, "Dockerfile", include_local=True)
    assert any(r.target == "https://app.datadoghq.com/agent" for r in docker_refs)


def test_dependency_extractors_cargo_go_and_package_assets() -> None:
    """Verify Cargo.toml, go.mod, and package asset parsers."""
    from devops_cli.security.reference_extractor import (
        _extract_cargo_dependencies,
        _extract_go_mod_dependencies,
        is_package_repository_asset,
    )

    # Cargo dependencies
    cargo_toml = (
        '[dependencies]\nserde = "1.0"\ntokio = { version = "1.28", features = ["full"] }\n'
    )
    cargo_lines = cargo_toml.splitlines()
    cargo_deps = _extract_cargo_dependencies(cargo_toml, cargo_lines, "Cargo.toml")
    assert len(cargo_deps) == 2
    assert any(d.name == "serde" for d in cargo_deps)
    assert any(d.name == "tokio" for d in cargo_deps)

    # Go mod dependencies
    go_mod = """module example.com/app

go 1.22

require (
\tgithub.com/gin-gonic/gin v1.9.1
\tgithub.com/google/uuid v1.6.0
)

require golang.org/x/crypto v0.21.0
"""
    go_lines = go_mod.splitlines()
    go_deps = _extract_go_mod_dependencies(go_lines, "go.mod")
    assert len(go_deps) == 3
    assert any("gin" in d.name for d in go_deps)

    # Package repository asset checks
    assert (
        is_package_repository_asset("https://files.pythonhosted.org/packages/package.whl") is True
    )
    assert (
        is_package_repository_asset("https://crates.io/api/v1/crates/tokio/1.28.0/download") is True
    )
    assert is_package_repository_asset("https://api.github.com/repos/org/repo/releases") is True


def test_extract_package_json_and_manifest_dispatch() -> None:
    """Verify package.json parsing and general manifest dispatcher."""
    import json

    from devops_cli.security.reference_extractor import (
        _extract_cargo_dependencies,
        _extract_package_json_dependencies,
        extract_dependencies_from_text,
    )

    pkg_json = json.dumps(
        {
            "dependencies": {"react": "^18.2.0"},
            "devDependencies": {"typescript": "^5.0.0"},
            "peerDependencies": {"react-dom": "^18.2.0"},
            "optionalDependencies": {"fsevents": "^2.3.2"},
        }
    )
    deps = _extract_package_json_dependencies(pkg_json, pkg_json.splitlines(), "package.json")
    assert len(deps) == 4
    assert any(d.name == "react" for d in deps)
    assert any(d.name == "typescript" for d in deps)

    # Invalid JSON
    assert _extract_package_json_dependencies("invalid json", [], "package.json") == []

    # Invalid Cargo TOML
    assert _extract_cargo_dependencies("invalid = [toml", [], "Cargo.toml") == []

    # Dispatcher
    pypi_deps = extract_dependencies_from_text("typer>=0.9.0\npydantic\n", "requirements.txt")
    assert len(pypi_deps) == 2
    assert extract_dependencies_from_text("foo", "unknown.manifest") == []
