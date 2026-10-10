"""Unit tests for dependency and network reference extractors."""

from __future__ import annotations

import pytest

from devops_cli.models.vulnerability import NetworkReference
from devops_cli.security.reference_extractor import (
    deduplicate_network_references,
    extract_dependencies_from_text,
    extract_network_references,
    is_public_ip,
    sort_network_references,
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
    Local cluster: http://localhost:8080/v1
    Test host: localhost
    Example doc: example.com
    External endpoint: https://auth.vendor-service.io/oauth/token
    Bare domain reference: prod-infra.custom-cloud.io
    File reference: main.py, coverage.xml, dmypy.json, config.yaml (should all be skipped)
    """
    refs = extract_network_references(doc, "docs/deploy.md")
    targets = {r.target: r for r in refs}

    # External targets
    target_api = targets.get("https://api.prod.example-corp.com/v1")
    assert target_api is not None
    assert (target_api.is_local, target_api.scope) == (False, "external")

    target_ip = targets.get("93.184.216.34")
    assert target_ip is not None
    assert (target_ip.is_local, target_ip.scope) == (False, "external")

    target_auth = targets.get("https://auth.vendor-service.io/oauth/token")
    assert target_auth is not None
    assert (target_auth.is_local, target_auth.scope) == (False, "external")

    # Local targets
    target_local_ip = targets.get("192.168.1.100")
    assert target_local_ip is not None
    assert (target_local_ip.is_local, target_local_ip.scope) == (True, "local")
    assert "Local" in target_local_ip.security_status

    target_local_url = targets.get("http://localhost:8080/v1")
    assert target_local_url is not None
    assert (target_local_url.is_local, target_local_url.scope) == (True, "local")

    # Bare words and RFC 2606 example domains must NOT be listed
    assert targets.get("localhost") is None
    assert targets.get("prod-infra.custom-cloud.io") is None
    assert targets.get("example.com") is None

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

    # Should find legitimate URLs
    assert any(t == "https://api.example-service.com" for t in targets)
    assert any(t == "https://custom-cloud.io/v1/metrics" for t in targets)
    # Bare words without scheme are not extracted
    assert "metrics.internal-monitoring.net" not in targets

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
    # Bare words without scheme are not extracted
    assert "api.custom-vendor.org" not in targets
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
    # ghcr.io is a bare word, not a URL with scheme
    assert "ghcr.io" not in targets_yaml

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
    assert "prod-infra.custom-cloud.io" not in targets_py


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

    # Bare words without scheme are not extracted as references
    assert targets_json.get("gateway.production-cloud.net") is None

    t_pub_ip = targets_json.get("93.184.216.34")
    assert t_pub_ip is not None
    assert not t_pub_ip.is_local

    t_int_ip = targets_json.get("10.0.0.5")
    assert t_int_ip is not None
    assert (t_int_ip.is_local, t_int_ip.scope) == (True, "local")

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
    # Bare words without scheme are not extracted
    assert targets_yaml.get("traces.custom-service.io") is None
    assert targets_yaml.get("8.8.8.8") is not None


def test_extract_network_references_local_and_reserved_spaces() -> None:
    """Test extraction of RFC reserved domains, local URLs, and private IP spaces."""
    doc = """
    # Local & Internal Services
    Localhost API: http://localhost:8080/v1
    Cluster DNS: jaeger.otel.svc.cluster.local
    Internal node: node1.corp.internal
    Home LAN: server.lan
    Private IP: 192.168.1.1
    Loopback: 127.0.0.1
    Reserved domain: example.com
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

    # Bare words without scheme or IP literals are not extracted
    assert targets.get("example.com") is None
    assert targets.get("jaeger.otel.svc.cluster.local") is None
    assert targets.get("node1.corp.internal") is None
    assert targets.get("server.lan") is None


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
    template1 = "*.tfvars.example"
    template2 = "*.env.example"
    lib_symbol = "rich.live.Live"
    pydantic_symbol = "pydantic.BaseModel"
    pytest_symbol = "pytest.mark.asyncio"
    click_symbol = "click.command"

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

    # Workspace files, wildcard templates, and installed packages must NOT be matched as external domains
    assert "auth.py" not in targets
    assert "server.py" not in targets
    assert "logging.py" not in targets
    assert "test_reference_extractor.py" not in targets
    assert "review.py" not in targets
    assert "*.tfvars.example" not in targets
    assert "*.env.example" not in targets
    assert "rich.live.live" not in targets
    assert "pydantic.basemodel" not in targets
    assert "pytest.mark.asyncio" not in targets
    assert "click.command" not in targets

    # Bare words are not extracted
    assert "metrics.telemetry-cloud.io" not in targets
    # Legitimate URL is extracted
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
        target="https://example.com",
        reference_type="url",
        source_file="src/client.py",
        line_number=88,
    )
    assert net_with_line.location == "src/client.py:88"


def test_extract_network_references_package_files_and_lockfile_filtering() -> None:
    from devops_cli.security.reference_extractor import (
        is_lockfile_or_ignore_file,
        is_trusted_registry_host,
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

    # Trusted package repository hosts should be recognized
    assert is_trusted_registry_host("files.pythonhosted.org")
    assert is_trusted_registry_host("registry.npmjs.org")
    assert is_trusted_registry_host("crates.io")
    assert is_trusted_registry_host("repo.maven.apache.org")
    assert not is_trusted_registry_host("api.my-vendor-service.io")
    assert not is_trusted_registry_host("evil-host.xyz")

    # In source files, package file download URLs from trusted registries are skipped
    # while legitimate service endpoints and arbitrary downloads are kept
    src_content = """
    pypi_wheel = "https://files.pythonhosted.org/packages/4c/76/pkg-1.0.0.whl"
    npm_tarball = "https://registry.npmjs.org/lib/-/lib-2.0.0.tgz"
    service_api = "https://api.external-monitoring-service.net/v2/events"
    arbitrary_download = "https://evil-host.xyz/payload.tar.gz"
    """
    refs_src = extract_network_references(src_content, "src/worker.py")
    targets = {r.target for r in refs_src}
    assert any(t == "https://api.external-monitoring-service.net/v2/events" for t in targets)
    assert any(t == "https://evil-host.xyz/payload.tar.gz" for t in targets)
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
    Legitimate URLs: https://api.datadoghq.com/v1 and https://auth.auth0.com/oauth/token.
    """
    refs = extract_network_references(doc_content, "docs/architecture.md")
    targets = {r.target for r in refs}

    # Legitimate external URLs are extracted
    assert any(t == "https://api.datadoghq.com/v1" for t in targets)
    assert any(t == "https://auth.auth0.com/oauth/token" for t in targets)

    # Bare words and source files should NOT be extracted as domains
    assert "api.datadoghq.com" not in targets
    assert "auth.auth0.com" not in targets
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


def test_token_string_parsing() -> None:
    """Verify safe literal string token parsing."""
    from devops_cli.security.reference_extractor import _parse_python_token_string

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
        is_trusted_registry_host,
    )

    # 1. Lockfiles and ignore files
    assert is_lockfile_or_ignore_file("poetry.lock") is True
    assert is_lockfile_or_ignore_file("pnpm-lock.yaml") is True
    assert is_lockfile_or_ignore_file(".dockerignore") is True
    assert is_lockfile_or_ignore_file("main.py") is False

    # 2. Package repository registry hosts
    assert is_trusted_registry_host("registry.npmjs.org") is True
    assert is_trusted_registry_host("crates.io") is True
    assert is_trusted_registry_host("app.datadoghq.com") is False

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
    json_strs = _extract_json_strings('{"server": "https://example.com", "port": 8080}')
    assert any(s[0] == "https://example.com" for s in json_strs)

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
        is_trusted_registry_host,
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
    assert is_trusted_registry_host("files.pythonhosted.org") is True
    assert is_trusted_registry_host("crates.io") is True
    assert is_trusted_registry_host("pypi.org") is True
    assert is_trusted_registry_host("api.github.com") is True
    assert is_trusted_registry_host("example.com") is False


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


def test_extract_network_references_edge_cases() -> None:
    content = """
    # Network targets
    export PROMETHEUS_ENDPOINT="http://prometheus.internal:9090/metrics"
    export GRAFANA_HOST="https://grafana.prod.corp.com"
    export PUBLIC_API="https://api.external-service.net/v1"
    CONNECT_IP = "93.184.216.34"
    LOCAL_IP = "127.0.0.1"
    """
    refs = extract_network_references(content, "deploy.py")
    assert len(refs) >= 2
    targets = [r.target for r in refs]
    assert any("https://api.external-service.net/v1" in t for t in targets)
    assert any("93.184.216.34" in t for t in targets)


def test_reference_extractor_advanced_edge_cases() -> None:
    """Verify is_local_or_reserved_domain suffixes and single-label URLs."""
    from devops_cli.security.reference_extractor import (
        extract_network_references,
        is_local_or_reserved_domain,
    )

    # 1. is_local_or_reserved_domain suffixes
    assert is_local_or_reserved_domain("node.cluster.local") is True
    assert is_local_or_reserved_domain("router.lan") is True
    assert is_local_or_reserved_domain("device.home.arpa") is True
    assert is_local_or_reserved_domain("host.localdomain") is True
    assert is_local_or_reserved_domain("invalid-domain-") is False
    assert is_local_or_reserved_domain("has_underscore.internal") is False

    # 2. Extract network references with mock single-label URL
    mock_refs = extract_network_references(
        "url = 'http://node1:11434'", "test.py", include_local=True
    )
    assert any(
        r.target == "http://node1:11434" and r.is_local is True and r.scope == "local"
        for r in mock_refs
    )


def test_reference_extractor_documented_examples_and_rfc_exclusions() -> None:
    """Verify RFC 2606/6761/6890/5737/3849 example domains, IPs, and phone exclusions."""
    from devops_cli.security.reference_extractor import (
        is_example_ip,
        is_example_or_invalid_domain,
        is_example_or_invalid_network_target,
        is_example_or_reserved_ip,
        is_example_phone_number,
        is_public_ip,
    )

    # 1. RFC 2606 reserved domains and TLDs
    rfc2606_domains = [
        "example.com",
        "sub.deep.example.net",
        "sample.example.org",
        "test.example.edu",
        "service.example",
        "broken.invalid",
        "staging.test",
    ]
    for d in rfc2606_domains:
        assert is_example_or_invalid_domain(d) is True, f"Failed for domain: {d}"
        assert is_example_or_invalid_network_target(d) is True, f"Failed network target: {d}"

    # Non-example domains (including valid local endpoints like localhost) must return False
    assert is_example_or_invalid_domain("localhost") is False
    assert is_example_or_invalid_domain("app.localhost") is False
    assert is_example_or_invalid_domain("worker.internal") is False
    assert is_example_or_invalid_domain("gateway.home.arpa") is False
    assert is_example_or_invalid_domain("github.com") is False
    assert is_example_or_invalid_domain("api.cloudflare.com") is False
    assert is_example_or_invalid_domain("openai.com") is False

    # 2. RFC 5737 IPv4 documentation spaces
    test_net_ips = [
        "192.0.2.1",  # TEST-NET-1
        "192.0.2.254",
        "198.51.100.1",  # TEST-NET-2
        "198.51.100.50",
        "203.0.113.1",  # TEST-NET-3
        "203.0.113.254",
    ]
    for ip in test_net_ips:
        assert is_example_ip(ip) is True, f"Failed is_example_ip: {ip}"
        assert is_example_or_reserved_ip(ip) is True, f"Failed is_example_or_reserved_ip: {ip}"
        assert is_public_ip(ip) is False, f"Should not be public IP: {ip}"
        assert is_example_or_invalid_network_target(ip) is True

    # 3. RFC 3849 & IAB Statement IPv6 documentation spaces
    ipv6_doc_ips = [
        "2001:db8::1",
        "2001:db8:85a3::8a2e:370:7334",
        "2001:db8:ffff:ffff:ffff:ffff:ffff:ffff",
    ]
    for ip in ipv6_doc_ips:
        assert is_example_ip(ip) is True, f"Failed IPv6 is_example_ip: {ip}"
        assert is_example_or_reserved_ip(ip) is True
        assert is_public_ip(ip) is False
        assert is_example_or_invalid_network_target(ip) is True

    # 4. RFC 6890 / Special IPv4 & IPv6 blocks (CGNAT, Benchmarking, Discard)
    special_ips = [
        "100.64.0.1",  # CGNAT RFC 6598
        "100.127.255.254",
        "198.18.0.1",  # Benchmarking RFC 2544
        "198.19.255.254",
        "100::1",  # Discard prefix RFC 6666
        "2001:2::1",  # IPv6 Benchmarking RFC 5180
    ]
    for ip in special_ips:
        assert is_example_or_reserved_ip(ip) is True, f"Failed special IP: {ip}"
        assert is_public_ip(ip) is False
        assert is_example_or_invalid_network_target(ip) is True

    # 5. Public IPs must be recognized correctly
    public_ips = ["8.8.8.8", "1.1.1.1", "93.184.216.34"]
    for ip in public_ips:
        assert is_example_ip(ip) is False
        assert is_example_or_reserved_ip(ip) is False
        assert is_public_ip(ip) is True
        assert is_example_or_invalid_network_target(ip) is False

    # 6. ATIS-0300115 / NANPA and UK Ofcom fictitious phone numbers
    fictitious_phones = [
        "555-0142",
        "+1-212-555-0199",
        "1-800-555-0100",
        "(212) 555-0123",
        "01632 960001",
        "+44 1632 4960123",
    ]
    for phone in fictitious_phones:
        assert is_example_phone_number(phone) is True, f"Failed phone: {phone}"

    # Real/ordinary numbers
    assert is_example_phone_number("212-555-1212") is False
    assert is_example_phone_number("1-800-222-3333") is False

    # 7. extract_network_references with exclude_examples=True vs exclude_examples=False
    sample_doc = """
    # Example Configuration
    Documentation URL: https://example.com/v1/health
    Example IP: 192.0.2.1
    Benchmarking IP: 198.18.1.10
    IPv6 Doc IP: 2001:db8::42
    Real Public IP: 93.184.216.34
    Real Service: https://api.custom-service.io/v1
    Contact: +1-212-555-0142
    """

    # With exclude_examples=False (default): example targets tagged with is_example=True
    refs_all = extract_network_references(sample_doc, "sample.md", exclude_examples=False)
    target_map = {r.target: r for r in refs_all}

    assert "https://example.com/v1/health" in target_map
    assert target_map["https://example.com/v1/health"].is_example is True
    assert (
        "✓ Safe (Documented Example)" in target_map["https://example.com/v1/health"].security_status
    )

    assert "192.0.2.1" in target_map
    assert target_map["192.0.2.1"].is_example is True
    assert "✓ Safe (Documented Example)" in target_map["192.0.2.1"].security_status

    assert "93.184.216.34" in target_map
    assert target_map["93.184.216.34"].is_example is False
    assert "https://api.custom-service.io/v1" in target_map

    # With exclude_examples=True: example targets completely omitted
    refs_filtered = extract_network_references(sample_doc, "sample.md", exclude_examples=True)
    filtered_targets = {r.target for r in refs_filtered}

    assert "https://example.com/v1/health" not in filtered_targets
    assert "192.0.2.1" not in filtered_targets
    assert "198.18.1.10" not in filtered_targets
    assert "2001:db8::42" not in filtered_targets
    assert "93.184.216.34" in filtered_targets
    assert "https://api.custom-service.io/v1" in filtered_targets


def test_network_references_rejects_unspecified_ip_and_example_domains() -> None:
    """Ensure 0.0.0.0, ::, RFC 2606 example domains, and bare words are rejected."""
    sample = """
    HOST = "0.0.0.0"
    V6_UNSPECIFIED = "::"
    TEST_ORG = "https://example.org"
    TEST_NET = "https://example.net"
    TEST_EDU = "https://example.edu"
    TEST_COM = "https://example.com"
    BARE_SPECIAL_TLD = "home.arpa"
    BARE_CLUSTER_TLD = "cluster.local"
    VALID_LOCAL = "argocd.example.internal"
    VALID_EXTERNAL = "api.github.com"
    VALID_LOCAL_URL = "http://argocd.example.internal:8080"
    VALID_EXTERNAL_URL = "https://api.custom-service.io/v1"
    """
    refs = extract_network_references(sample, "test_config.py", exclude_examples=True)
    targets = {r.target for r in refs}

    # Invalid entries and bare words MUST be rejected
    rejected = [
        "0.0.0.0",  # nosec B104  # the bind-all address, a value the extractor rejects
        "::",
        "https://example.org",
        "https://example.net",
        "https://example.edu",
        "https://example.com",
        "home.arpa",
        "cluster.local",
        "argocd.example.internal",
        "api.github.com",
    ]
    assert all(item not in targets for item in rejected)

    # Legitimate endpoints MUST be retained
    assert (
        "http://argocd.example.internal:8080" in targets,
        "https://api.custom-service.io/v1" in targets,
    ) == (True, True)


def test_network_references_splits_comma_separated_urls() -> None:
    """Ensure comma-separated URL lists are parsed into separate network references."""
    content = 'SERVERS = "http://node1:11434,http://node2:11434"'
    refs = extract_network_references(content, "test_urls.py")
    targets = {r.target for r in refs}
    assert "http://node1:11434" in targets
    assert "http://node2:11434" in targets
    assert "http://node1:11434,http://node2:11434" not in targets


def test_network_references_rejects_regex_patterns() -> None:
    """Ensure regex pattern strings with escaped domain syntax are not treated as URLs."""
    content = r'SLACK_REGEX = r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"'
    refs = extract_network_references(content, "test_sanitizer.py")
    targets = {r.target for r in refs}
    assert not any("hooks" in t for t in targets)


def test_python_literals_in_dict_keys_and_telemetry_calls() -> None:
    """Ensure URLs and IPs in dict keys and telemetry calls are extracted, but bare words are ignored."""
    code = """
    routes = {
        "https://api.example.internal/v1": "service_a",
        "8.8.8.8": "dns_server",
        "bare.domain.internal": "ignored",
    }
    record_metric("cli.command.total", 1.0)
    logfire.metric_counter("agent.tokens.total").add(10)
    counter("https://telemetry.custom-vendor.net/ingest")
    ping("1.1.1.1")
    """
    refs = extract_network_references(code, "service.py", include_local=True)
    targets = {r.target for r in refs}
    assert (
        "https://api.example.internal/v1" in targets,
        "8.8.8.8" in targets,
        "1.1.1.1" in targets,
        "https://telemetry.custom-vendor.net/ingest" in targets,
    ) == (True, True, True, True)
    assert (
        "bare.domain.internal" not in targets,
        "cli.command.total" not in targets,
        "agent.tokens.total" not in targets,
    ) == (True, True, True)


def test_deduplicate_network_references() -> None:
    """Ensure duplicate references are merged and their locations consolidated."""
    ref1 = NetworkReference(
        target="http://example.com:8080",
        reference_type="url",
        source_file="src/devops_cli/config/defaults.py",
        line_number=125,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )
    ref2 = NetworkReference(
        target="http://example.com:8080",
        reference_type="url",
        source_file="src/devops_cli/config/defaults.py",
        line_number=324,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )
    ref3 = NetworkReference(
        target="https://api.github.com",
        reference_type="url",
        source_file="src/devops_cli/github/client.py",
        line_number=45,
        security_status="✓ Safe",
        is_local=False,
        scope="external",
    )
    deduped = deduplicate_network_references([ref1, ref2, ref3])
    assert len(deduped) == 2
    hl_ref = next(r for r in deduped if r.target == "http://example.com:8080")
    assert ("125" in hl_ref.location, "324" in hl_ref.location) == (True, True)


def test_sort_network_references_ordered() -> None:
    """Ensure audit results are sorted by:
    Scope (external, then local),
    Security (descending severity),
    Type (url, then ip),
    Target (ascending),
    Location (ascending).
    """
    ext_flagged = NetworkReference(
        target="https://malicious.example-bad.com",
        reference_type="url",
        source_file="src/bad.py",
        line_number=10,
        security_status="⚠️ Flagged (Malicious)",
        is_local=False,
        scope="external",
    )
    ext_safe_url = NetworkReference(
        target="https://api.vendor.com/v1",
        reference_type="url",
        source_file="src/api.py",
        line_number=20,
        security_status="✓ Safe",
        is_local=False,
        scope="external",
    )
    ext_safe_ip = NetworkReference(
        target="93.184.216.34",
        reference_type="ip",
        source_file="src/dns.py",
        line_number=5,
        security_status="✓ Safe",
        is_local=False,
        scope="external",
    )
    loc_url = NetworkReference(
        target="http://example.com:8080/argocd",
        reference_type="url",
        source_file="src/config.py",
        line_number=15,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )
    loc_ip = NetworkReference(
        target="192.168.49.2",
        reference_type="ip",
        source_file="src/k8s.py",
        line_number=30,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )

    unordered = [loc_ip, ext_safe_url, loc_url, ext_safe_ip, ext_flagged]
    ordered = sort_network_references(unordered)

    assert [r.scope for r in ordered] == [
        "external",
        "external",
        "external",
        "local",
        "local",
    ]
    assert tuple(ordered) == (
        ext_flagged,
        ext_safe_url,
        ext_safe_ip,
        loc_url,
        loc_ip,
    )


def test_no_dns_lookups_during_reference_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that reference extraction never invokes socket.getaddrinfo or performs DNS resolution."""
    import socket

    def exploding_getaddrinfo(*args: object, **kwargs: object) -> None:
        raise AssertionError("DNS lookup attempted during reference extraction!")

    monkeypatch.setattr(socket, "getaddrinfo", exploding_getaddrinfo)
    content = """
    export HOST="api.datadoghq.com"
    export URL="https://api.custom-service.io/v1"
    export IP="1.1.1.1"
    """
    refs = extract_network_references(content, "test.sh")
    targets = {r.target for r in refs}
    assert (
        "https://api.custom-service.io/v1" in targets,
        "1.1.1.1" in targets,
        "api.datadoghq.com" not in targets,
    ) == (True, True, True)


@pytest.mark.parametrize(
    "bare_word",
    [
        "localhost",
        "example.internal",
        "api.datadoghq.com",
        "ghcr.io",
        "host: db.vendor-x.io",
        "registry.npmjs.org",
        "pypi.org",
        "node1.cluster.local",
    ],
)
def test_bare_words_never_extracted_as_network_references(bare_word: str) -> None:
    """Ensure bare words, hostnames, and domain strings without URLs or IPs are never extracted."""
    content = f"target = '{bare_word}'\n"
    refs = extract_network_references(content, "config.py", include_local=True)
    assert refs == []


def test_any_scheme_url_reference_extraction() -> None:
    """Verify URL reference extraction across non-HTTP schemes and exclusions."""
    content = """
    REDIS_URL = "redis://user:pass@redis.example.internal:6379/0"
    PG_URL = "postgresql://pg.example.internal:5432/db"
    WS_URL = "wss://stream.vendor.com/live"
    GRPC_URL = "grpc://grpc.vendor.com:443"
    FILE_URL = "file:///tmp/something"
    JDBC_URL = "jdbc:postgresql://db.vendor.com/test"
    """
    refs = extract_network_references(content, "settings.py", include_local=True)
    targets = {r.target for r in refs}
    assert (
        "redis://user:pass@redis.example.internal:6379/0" in targets,
        "postgresql://pg.example.internal:5432/db" in targets,
        "wss://stream.vendor.com/live" in targets,
        "grpc://grpc.vendor.com:443" in targets,
        "file:///tmp/something" not in targets,
    ) == (True, True, True, True, True)


def test_download_url_registry_vs_arbitrary_host() -> None:
    """Ensure registry URLs are excluded by host only, while arbitrary hosts are kept."""
    pypi_url = "https://files.pythonhosted.org/packages/package.whl"
    crates_url = "https://crates.io/api/v1/crates/tokio/download"
    vendor_url = "https://downloads.vendor.com/package.whl"

    content = f'URLS = ["{pypi_url}", "{crates_url}", "{vendor_url}"]'
    refs = extract_network_references(content, "download.py")
    targets = {r.target for r in refs}
    assert (pypi_url not in targets, crates_url not in targets, vendor_url in targets) == (
        True,
        True,
        True,
    )
