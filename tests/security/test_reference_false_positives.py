"""What `extract_network_references` never reports: code, configuration keys, file names, bare
host names and patterns that look like names."""

from __future__ import annotations

import pytest

from devops_cli.security.reference_extractor import extract_network_references


def _targets(content: str, file_name: str, **options: bool) -> set[str]:
    return {r.target for r in extract_network_references(content, file_name, **options)}


def test_a_gitignore_gives_no_reference() -> None:
    """Ignore patterns and file names are not network targets."""
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
    assert extract_network_references(gitignore_content, ".gitignore") == []


def test_python_imports_calls_and_attributes_are_not_references() -> None:
    """Imports, method chains, attributes and calls are code; only the URL literals count."""
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
    targets = _targets(python_code, "src/service/client.py")

    assert {"https://api.example-service.com", "https://custom-cloud.io/v1/metrics"} <= targets
    assert targets.isdisjoint(
        {
            "metrics.internal-monitoring.net",
            "logging.getlogger",
            "self.settings",
            "self.sdk",
            "self.authenticated",
            "logger.debug",
            "self.sdk.get.sites",
            "res.get",
            "pytest.raises",
            "runner.invoke",
            "unittest.mock",
        }
    )


def test_toml_table_headers_are_not_references() -> None:
    """`[tool.ruff]` and the like are table names, and a bare host value is not a reference."""
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
    targets = _targets(toml_content, "pyproject.toml")

    assert "https://custom-vendor.org" in targets
    assert targets.isdisjoint(
        {"api.custom-vendor.org", "tool.ruff", "tool.ruff.lint", "tool.pytest", "tool.mypy"}
    )


def test_workflow_git_config_keys_and_a_bare_registry_name_are_not_references() -> None:
    """`user.email`, `user.name` and a registry name with no scheme are not targets."""
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
    targets = _targets(workflow_yaml, ".github/workflows/release.yml")

    assert targets.isdisjoint({"user.email", "user.name", "ghcr.io"})


def test_mock_patch_paths_and_module_names_are_not_references() -> None:
    """Dotted patch targets, module paths, attributes and requirement file names are code."""
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
    targets = _targets(py_content, "tests/test_mock.py")

    assert targets.isdisjoint(
        {
            "devops_cli.commands.workspace.subprocess.run",
            "devops_cli.ai.agents.pipeline.multiagentpipeline.run",
            "m.group",
            "commands.ai",
            "self.host",
            "requirements.in",
            "prod-infra.custom-cloud.io",
        }
    )


def test_terraform_attribute_references_are_not_references() -> None:
    """`aws_route_table.public.id` and the like are Terraform expressions."""
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
    targets = _targets(tf_content, "tf/aws/main.tf")

    assert targets.isdisjoint({"nat.id", "igw.id", "public.id", "eks.name"})


def test_python_import_paths_are_not_references() -> None:
    """Module paths in imports are not host names."""
    py_imports = """
    from collections.abc import Sequence
    from devops_cli.models.ai import FileAnalysisMeta
    import httpx.client.post
    """
    targets = _targets(py_imports, "src/devops_cli/foo.py")

    assert targets.isdisjoint({"collections.abc", "models.ai", "httpx.client.post"})


def test_function_calls_file_names_and_package_symbols_are_not_references() -> None:
    """Calls, workspace file names, wildcard templates, package symbols and bare names are not
    references; the URL is."""
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
    targets = _targets(content, "src/devops_cli/example.py")

    assert "https://dashboard.production-network.net/status" in targets
    assert targets.isdisjoint(
        {
            "not.a.domain.com",
            "service.client.call",
            "helper.utils.format",
            "auth.py",
            "server.py",
            "logging.py",
            "test_reference_extractor.py",
            "review.py",
            "*.tfvars.example",
            "*.env.example",
            "rich.live.live",
            "pydantic.basemodel",
            "pytest.mark.asyncio",
            "click.command",
            "metrics.telemetry-cloud.io",
        }
    )


def test_source_file_names_and_span_attribute_names_are_not_references() -> None:
    """File names with source extensions and telemetry attribute names are not host names; the
    URLs in the same text are references."""
    doc_content = """
    # Architecture & Agent Rules
    See intelligence.py, manager.py, misc.py, common.py, helpers.py.
    Also check postcreate.sh, architect.md, devsecops.md, vpc.tf, lib.rs, git-daemon.pid.
    Span attributes: service.name, ci.step.security, host.name, process.pid, concurrency.group.
    Legitimate domain: api.datadoghq.com and auth.auth0.com.
    Legitimate URLs: https://api.datadoghq.com/v1 and https://auth.auth0.com/oauth/token.
    """
    targets = _targets(doc_content, "docs/architecture.md")

    assert {"https://api.datadoghq.com/v1", "https://auth.auth0.com/oauth/token"} <= targets
    assert targets.isdisjoint(
        {
            "api.datadoghq.com",
            "auth.auth0.com",
            "intelligence.py",
            "manager.py",
            "postcreate.sh",
            "architect.md",
            "devsecops.md",
            "vpc.tf",
            "lib.rs",
            "git-daemon.pid",
            "service.name",
            "ci.step.security",
            "host.name",
            "process.pid",
            "concurrency.group",
        }
    )


def test_unspecified_addresses_example_domains_and_bare_names_are_rejected() -> None:
    """With examples excluded, the unspecified addresses, the RFC 2606 domains and bare names are
    not references; a local and an external URL are."""
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
    targets = _targets(sample, "test_config.py", exclude_examples=True)

    rejected = {
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
    }
    assert (
        targets.isdisjoint(rejected),
        "http://argocd.example.internal:8080" in targets,
        "https://api.custom-service.io/v1" in targets,
    ) == (True, True, True)


def test_a_regex_with_escaped_dots_is_not_a_url() -> None:
    """A pattern such as `https://hooks\\.slack\\.com/...` is a regex, not a reference."""
    content = r'SLACK_REGEX = r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"'

    assert not any("hooks" in t for t in _targets(content, "test_sanitizer.py"))


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
    """Bare words, host names and domain strings with no scheme and no IP are never references."""
    content = f"target = '{bare_word}'\n"

    assert extract_network_references(content, "config.py", include_local=True) == []
