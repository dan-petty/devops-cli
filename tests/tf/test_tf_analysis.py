"""Unit tests for in-process HCL AST analysis, state introspection, and drift detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.tf import app as tf_app
from devops_cli.tf import analysis as tf_analysis
from devops_cli.tf.analysis import (
    analyze_directory,
    build_dependency_graph,
    compute_blast_radius,
    detect_drift,
    extract_references,
    holds_local_resource_state,
    parse_hcl_directory,
)

is_directory_initialized: Any = getattr(tf_analysis, "is_directory_initialized", None)
parse_plan_drift: Any = getattr(tf_analysis, "parse_plan_drift", None)
parse_show_state: Any = getattr(tf_analysis, "parse_show_state", None)
read_plan_drift: Any = getattr(tf_analysis, "read_plan_drift", None)
read_state: Any = getattr(tf_analysis, "read_state", None)

runner = CliRunner()

_MAIN_TF = """
variable "region" { default = "us-east-1" }

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "app" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}

resource "aws_instance" "web" {
  subnet_id  = aws_subnet.app.id
  depends_on = [aws_vpc.main]
}

data "aws_ami" "ubuntu" {
  most_recent = true
}

module "db" {
  source = "./modules/db"
  vpc_id = aws_vpc.main.id
}

output "vpc_id" { value = aws_vpc.main.id }
"""

_SHOW_STATE = {
    "format_version": "1.0",
    "terraform_version": "1.9.0",
    "serial": 12,
    "lineage": "abc-123",
    "values": {
        "root_module": {
            "resources": [
                {
                    "address": "aws_vpc.main",
                    "mode": "managed",
                    "type": "aws_vpc",
                    "name": "main",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "values": {"cidr_block": "10.0.0.0/16"},
                },
                {
                    "address": "aws_s3_bucket.legacy",
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "name": "legacy",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "values": {"bucket": "legacy"},
                },
            ]
        },
        "outputs": {"vpc_id": {"value": "vpc-1"}},
    },
}


@pytest.fixture
def tf_dir(tmp_path: Path) -> Path:
    """Provide a configuration directory containing a representative HCL manifest."""
    (tmp_path / "main.tf").write_text(_MAIN_TF, encoding="utf-8")
    return tmp_path


@pytest.fixture
def tf_dir_with_state(tf_dir: Path) -> Path:
    """Provide an initialized configuration directory alongside recorded state."""
    (tf_dir / ".terraform").mkdir(parents=True, exist_ok=True)
    return tf_dir


@pytest.fixture(autouse=True)
def _stub_tf_show_for_state(process_fake: Any) -> None:
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        lambda call: "show" in call.argv and "-json" in call.argv,
        ProcessAnswer(stdout=json.dumps(_SHOW_STATE)),
    )
    process_fake.answer(
        lambda call: "plan" in call.argv and "-refresh-only" in call.argv,
        ProcessAnswer(stdout=""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. HCL parsing
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_hcl_directory_projects_declarations(tf_dir: Path) -> None:
    """Resources, data sources, modules, variables, and outputs are all projected."""
    config = parse_hcl_directory(tf_dir)

    assert [r.address for r in config.resources] == [
        "aws_vpc.main",
        "aws_subnet.app",
        "aws_instance.web",
        "data.aws_ami.ubuntu",
    ]
    assert (
        [m.address for m in config.modules],
        config.variables,
        config.outputs,
        config.parsed_files,
        config.failed_files,
    ) == (["module.db"], ["region"], ["vpc_id"], ["main.tf"], {})


def test_parsed_resources_carry_provider_and_source(tf_dir: Path) -> None:
    """Each declaration records its source file and empty provider when unstated."""
    vpc = next(r for r in parse_hcl_directory(tf_dir).resources if r.address == "aws_vpc.main")
    assert (vpc.provider, vpc.source_file, vpc.block_type, vpc.resource_type, vpc.name) == (
        "",
        "main.tf",
        "resource",
        "aws_vpc",
        "main",
    )


def test_parsed_resources_record_explicit_provider(tmp_path: Path) -> None:
    """An explicit provider or alias is recorded without prefix guessing."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_vpc" "west" { provider = aws.west }\n', encoding="utf-8"
    )
    res = parse_hcl_directory(tmp_path).resources[0]
    assert res.provider == "aws.west"


def test_string_literals_are_unquoted(tf_dir: Path) -> None:
    """Attribute values are normalised out of the quoting python-hcl2 preserves."""
    vpc = next(r for r in parse_hcl_directory(tf_dir).resources if r.address == "aws_vpc.main")
    assert vpc.attributes["cidr_block"] == "10.0.0.0/16"
    assert "__is_block__" not in vpc.attributes


def test_data_sources_are_addressed_with_the_data_prefix(tf_dir: Path) -> None:
    """Data sources use their canonical `data.<type>.<name>` address."""
    data_source = next(r for r in parse_hcl_directory(tf_dir).resources if r.block_type == "data")
    assert (data_source.address, data_source.name) == ("data.aws_ami.ubuntu", "ubuntu")


def test_malformed_file_is_recorded_without_aborting_the_scan(tf_dir: Path) -> None:
    """One unparseable manifest must not hide the rest of the configuration."""
    (tf_dir / "broken.tf").write_text('resource "aws_vpc" "x" {', encoding="utf-8")
    config = parse_hcl_directory(tf_dir)

    assert "broken.tf" in config.failed_files
    assert "main.tf" in config.parsed_files
    assert any(r.address == "aws_vpc.main" for r in config.resources)


def test_missing_directory_yields_empty_configuration(tmp_path: Path) -> None:
    """A directory that does not exist parses to an empty configuration, not an error."""
    config = parse_hcl_directory(tmp_path / "absent")
    assert (config.resources, config.modules, config.parsed_files) == ([], [], [])


def test_non_hcl_files_are_ignored(tf_dir: Path) -> None:
    """Only `.tf` files are parsed; sibling files are left alone."""
    (tf_dir / "README.md").write_text("# not terraform", encoding="utf-8")
    (tf_dir / "terraform.tfvars").write_text('region = "eu-west-1"', encoding="utf-8")
    assert parse_hcl_directory(tf_dir).parsed_files == ["main.tf"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Reference extraction
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_references_finds_interpolated_addresses() -> None:
    """Interpolated traversals reduce to the address they depend upon."""
    assert extract_references("${aws_vpc.main.id}") == {"aws_vpc.main"}
    assert extract_references(["${aws_subnet.app.id}", "${aws_vpc.main}"]) == {
        "aws_subnet.app",
        "aws_vpc.main",
    }


def test_extract_references_handles_module_and_data_addresses() -> None:
    """Module and data traversals keep the namespace their address requires."""
    assert extract_references("${module.db.endpoint}") == {"module.db"}
    assert extract_references("${data.aws_ami.ubuntu.id}") == {"data.aws_ami.ubuntu"}


def test_extract_references_ignores_non_addressing_namespaces() -> None:
    """Variables, locals, and each-expressions do not address another resource."""
    assert extract_references("${var.region}") == set()
    assert extract_references("${local.tags}") == set()
    assert extract_references("${each.key}") == set()
    assert extract_references("${count.index}") == set()
    assert extract_references("${path.module}") == set()


def test_extract_references_ignores_plain_values() -> None:
    """Literals and non-string values contribute no dependency edges."""
    assert extract_references("10.0.0.0/16") == set()
    assert extract_references(42) == set()
    assert extract_references(None) == set()


def test_extract_references_walks_nested_structures() -> None:
    """References are found inside nested maps and lists."""
    value = {"tags": {"owner": "${aws_vpc.main.id}"}, "subnets": [{"id": "${aws_subnet.app.id}"}]}
    assert extract_references(value) == {"aws_vpc.main", "aws_subnet.app"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dependency graph & blast radius
# ─────────────────────────────────────────────────────────────────────────────


def test_dependency_graph_includes_interpolation_and_depends_on(tf_dir: Path) -> None:
    """Both interpolated references and explicit depends_on become graph edges."""
    graph = build_dependency_graph(parse_hcl_directory(tf_dir))

    assert graph["aws_subnet.app"] == ["aws_vpc.main"]
    assert graph["aws_instance.web"] == ["aws_subnet.app", "aws_vpc.main"]
    assert (graph["aws_vpc.main"], graph["module.db"]) == ([], ["aws_vpc.main"])


def test_dependency_graph_excludes_undeclared_addresses(tmp_path: Path) -> None:
    """References to resources declared elsewhere do not create phantom nodes."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_subnet" "app" { vpc_id = aws_vpc.elsewhere.id }', encoding="utf-8"
    )
    graph = build_dependency_graph(parse_hcl_directory(tmp_path))
    assert graph == {"aws_subnet.app": []}


def test_blast_radius_traverses_transitive_dependents(tmp_path: Path) -> None:
    """Impact propagates through a dependency chain, not just direct references."""
    (tmp_path / "main.tf").write_text(
        """
        resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
        resource "aws_subnet" "app" { vpc_id = aws_vpc.main.id }
        resource "aws_instance" "web" { subnet_id = aws_subnet.app.id }
        """,
        encoding="utf-8",
    )
    graph = build_dependency_graph(parse_hcl_directory(tmp_path))
    radius = compute_blast_radius(graph, "aws_vpc.main")

    assert (radius.direct_dependents, radius.transitive_dependents, radius.impact_count) == (
        ["aws_subnet.app"],
        ["aws_instance.web", "aws_subnet.app"],
        2,
    )


def test_blast_radius_of_a_leaf_is_empty(tf_dir: Path) -> None:
    """A resource nothing depends on has no blast radius but keeps its dependencies."""
    graph = build_dependency_graph(parse_hcl_directory(tf_dir))
    radius = compute_blast_radius(graph, "aws_instance.web")

    assert (radius.direct_dependents, radius.impact_count, radius.depends_on) == (
        [],
        0,
        ["aws_subnet.app", "aws_vpc.main"],
    )


def test_blast_radius_terminates_on_a_dependency_cycle(tmp_path: Path) -> None:
    """A cyclic configuration is traversed without looping forever."""
    (tmp_path / "main.tf").write_text(
        """
        resource "aws_a" "one" { peer = aws_b.two.id }
        resource "aws_b" "two" { peer = aws_a.one.id }
        """,
        encoding="utf-8",
    )
    graph = build_dependency_graph(parse_hcl_directory(tmp_path))
    radius = compute_blast_radius(graph, "aws_a.one")
    assert radius.transitive_dependents == ["aws_b.two"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. State introspection
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_show_state_projects_typed_records() -> None:
    """State metadata and resource records project into typed models."""
    state = parse_show_state(_SHOW_STATE)

    assert (state.version, state.terraform_version, state.serial, state.lineage) == (
        1,
        "1.9.0",
        12,
        "abc-123",
    )
    assert [(r.address, r.instance_count) for r in state.resources] == [
        ("aws_vpc.main", 1),
        ("aws_s3_bucket.legacy", 1),
    ]
    assert state.outputs["vpc_id"]["value"] == "vpc-1"


def test_read_state_returns_none_without_an_initialized_directory(tf_dir: Path) -> None:
    """A configuration directory without .terraform has no state to read."""
    assert (read_state(tf_dir), is_directory_initialized(tf_dir)) == (None, False)


@pytest.mark.parametrize(
    ("state_files", "expected"),
    [
        ({}, False),
        ({"terraform.tfstate": '{"version": 4, "resources": []}'}, True),
        ({".terraform/terraform.tfstate": '{"version": 4, "resources": []}'}, True),
        ({".terraform/terraform.tfstate": '{"version": 3, "backend": {"type": "s3"}}'}, False),
        ({".terraform/terraform.tfstate": "{not json"}, True),
        (
            {
                ".terraform/terraform.tfstate": '{"version": 3, "backend": {"type": "local"}}',
                "terraform.tfstate": '{"version": 4, "resources": []}',
            },
            True,
        ),
    ],
    ids=["none", "beside-config", "legacy-dot-terraform", "backend-cache", "unreadable", "local"],
)
def test_local_resource_state_excludes_the_backend_configuration_cache(
    tf_dir: Path, state_files: dict[str, str], expected: bool
) -> None:
    """`init` caches a configured backend in `.terraform/terraform.tfstate`; that file holds
    no resources, so only a state file without a `backend` section counts as local state."""
    for name, text in state_files.items():
        (tf_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (tf_dir / name).write_text(text, encoding="utf-8")

    assert holds_local_resource_state(tf_dir) is expected


def test_parse_show_state_tolerates_malformed_json() -> None:
    """A corrupt show payload degrades to an empty state rather than raising."""
    assert parse_show_state("{not json").resources == []


def test_show_state_data_sources_use_the_data_prefix() -> None:
    """Data sources recorded in show state keep their canonical addressing."""
    payload = {
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "data.aws_ami.ubuntu",
                        "mode": "data",
                        "type": "aws_ami",
                        "name": "ubuntu",
                    }
                ]
            }
        }
    }
    state = parse_show_state(payload)
    assert state.resources[0].address == "data.aws_ami.ubuntu"


def test_show_state_records_module_scoped_addresses() -> None:
    """Resources inside a module keep their module path in the address."""
    payload = {
        "values": {
            "root_module": {
                "child_modules": [
                    {
                        "address": "module.db",
                        "resources": [
                            {
                                "address": "module.db.aws_db_instance.primary",
                                "mode": "managed",
                                "type": "aws_db_instance",
                                "name": "primary",
                            }
                        ],
                    }
                ]
            }
        }
    }
    state = parse_show_state(payload)
    assert state.resources[0].address == "module.db.aws_db_instance.primary"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Drift detection
# ─────────────────────────────────────────────────────────────────────────────


def test_detect_drift_reports_both_divergence_directions(tf_dir_with_state: Path) -> None:
    """Unapplied declarations and orphaned state records are both surfaced."""
    config, state = analyze_directory(tf_dir_with_state)
    report = detect_drift(config, state)

    assert (report.missing_from_state, report.orphaned_in_state, report.in_sync) == (
        ["aws_instance.web", "aws_subnet.app"],
        ["aws_s3_bucket.legacy"],
        ["aws_vpc.main"],
    )
    assert (report.drift_detected, report.state_present) == (True, True)


def test_detect_drift_excludes_data_sources(tf_dir_with_state: Path) -> None:
    """Data sources are reads, not managed resources, so they never count as drift."""
    config, state = analyze_directory(tf_dir_with_state)
    report = detect_drift(config, state)
    assert not any("data.aws_ami" in address for address in report.missing_from_state)


def test_detect_drift_without_state_marks_everything_pending(tf_dir: Path) -> None:
    """With no state file, every declared resource is pending apply."""
    config, state = analyze_directory(tf_dir)
    report = detect_drift(config, state)

    assert (report.state_present, report.state_count, report.declared_count) == (False, 0, 3)
    assert report.drift_detected is True


def test_detect_drift_reports_clean_when_aligned(tmp_path: Path) -> None:
    """Matching configuration and state report no drift."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }', encoding="utf-8"
    )
    config = parse_hcl_directory(tmp_path)
    state = parse_show_state(
        {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_vpc.main",
                            "mode": "managed",
                            "type": "aws_vpc",
                            "name": "main",
                        }
                    ]
                }
            }
        }
    )
    report = detect_drift(config, state)

    assert (report.drift_detected, report.in_sync) == (False, ["aws_vpc.main"])


# ─────────────────────────────────────────────────────────────────────────────
# 6. CLI commands
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_graph_renders_dependency_table(tf_dir: Path) -> None:
    """`devops tf graph` renders every address with its dependencies."""
    result = runner.invoke(tf_app, ["graph", str(tf_dir)])
    assert result.exit_code == 0
    assert "aws_subnet.app" in result.output
    assert "dependency edge" in result.output


def test_cli_graph_json_emits_the_graph(tf_dir: Path) -> None:
    """The JSON form emits the raw adjacency mapping."""
    result = runner.invoke(tf_app, ["graph", str(tf_dir), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["graph"]["aws_subnet.app"] == ["aws_vpc.main"]


def test_cli_graph_blast_radius_for_resource(tf_dir: Path) -> None:
    """Passing --resource switches to blast radius output."""
    result = runner.invoke(tf_app, ["graph", str(tf_dir), "--resource", "aws_vpc.main", "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["impact_count"] == 3


def test_cli_graph_rejects_unknown_resource(tf_dir: Path) -> None:
    """An address that is not declared exits non-zero with an actionable message."""
    result = runner.invoke(tf_app, ["graph", str(tf_dir), "--resource", "aws_vpc.absent"])
    assert result.exit_code == 1
    assert "not declared" in result.output


def test_cli_graph_reports_parse_failures(tf_dir: Path) -> None:
    """Unparseable manifests are named rather than silently omitted."""
    (tf_dir / "broken.tf").write_text('resource "aws_vpc" "x" {', encoding="utf-8")
    result = runner.invoke(tf_app, ["graph", str(tf_dir)])

    assert result.exit_code == 0
    assert "broken.tf" in result.output


def test_cli_drift_reports_divergence(tf_dir_with_state: Path) -> None:
    """`devops tf drift` lists both divergence directions."""
    result = runner.invoke(tf_app, ["drift", str(tf_dir_with_state)])

    assert result.exit_code == 0
    assert "aws_s3_bucket.legacy" in result.output
    assert "in state, not declared" in result.output


def test_cli_drift_json_output(tf_dir_with_state: Path) -> None:
    """The JSON form emits the typed drift report."""
    result = runner.invoke(tf_app, ["drift", str(tf_dir_with_state), "--json"])
    payload = json.loads(result.output)

    assert result.exit_code == 0
    assert payload["orphaned_in_state"] == ["aws_s3_bucket.legacy"]


def test_cli_drift_warns_when_state_absent(tf_dir: Path) -> None:
    """A configuration with no state reports that state is unavailable."""
    result = runner.invoke(tf_app, ["drift", str(tf_dir)])
    assert result.exit_code == 0
    assert "state unavailable (run tofu init)" in result.output.lower()


def test_cli_commands_support_dry_run(tf_dir: Path) -> None:
    """Both analysis commands run locally in dry run as no-external-request commands."""
    graph_result = runner.invoke(tf_app, ["graph", str(tf_dir)], env={"DEVOPS_CLI_DRY_RUN": "true"})
    drift_result = runner.invoke(tf_app, ["drift", str(tf_dir)], env={"DEVOPS_CLI_DRY_RUN": "true"})

    assert (graph_result.exit_code, drift_result.exit_code) == (0, 0)
    assert "IaC Resource Dependency Graph" in graph_result.output
    assert "state unavailable" in drift_result.output.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 7. OpenTofu CLI state inspection and live drift detection (#1437)
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_show_state_projects_child_modules_and_providers() -> None:
    """Recorded `tofu show -json` output projects root and child module resources with provider names."""
    from devops_cli.tf.analysis import parse_show_state

    show_payload = {
        "format_version": "1.0",
        "terraform_version": "1.9.0",
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_vpc.main",
                        "mode": "managed",
                        "type": "aws_vpc",
                        "name": "main",
                        "provider_name": "registry.terraform.io/hashicorp/aws",
                        "values": {"cidr_block": "10.0.0.0/16"},
                    }
                ],
                "child_modules": [
                    {
                        "address": "module.db",
                        "resources": [
                            {
                                "address": "module.db.aws_db_instance.primary",
                                "mode": "managed",
                                "type": "aws_db_instance",
                                "name": "primary",
                                "provider_name": "registry.terraform.io/hashicorp/aws",
                                "values": {"instance_class": "db.t3.micro"},
                            }
                        ],
                    }
                ],
            }
        },
    }
    state = parse_show_state(show_payload)
    assert len(state.resources) == 2
    vpc = next(r for r in state.resources if r.address == "aws_vpc.main")
    db = next(r for r in state.resources if r.address == "module.db.aws_db_instance.primary")
    assert vpc.provider == "registry.terraform.io/hashicorp/aws"
    assert (db.module, db.provider) == ("module.db", "registry.terraform.io/hashicorp/aws")


def test_parse_show_state_recovers_encrypted_state_resources() -> None:
    """Decrypted `tofu show -json` output populates state resources for an encrypted backend."""
    from devops_cli.tf.analysis import parse_show_state

    show_payload = {
        "format_version": "1.0",
        "terraform_version": "1.9.0",
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_vpc.secure",
                        "mode": "managed",
                        "type": "aws_vpc",
                        "name": "secure",
                        "provider_name": "registry.terraform.io/hashicorp/aws",
                        "values": {"cidr_block": "10.10.0.0/16"},
                    }
                ]
            }
        },
    }
    state = parse_show_state(show_payload)
    assert len(state.resources) == 1
    assert state.resources[0].address == "aws_vpc.secure"


def test_parse_plan_drift_extracts_drifted_addresses() -> None:
    """`tofu plan -refresh-only -json` output streams or structures extract drifted resource addresses."""
    event_stream = (
        '{"@level":"info","@message":"aws_vpc.main: Drift detected","type":"resource_drift",'
        '"change":{"resource":{"addr":"aws_vpc.main","resource_type":"aws_vpc","resource_name":"main"},"action":"update"}}\n'
        '{"@level":"info","@message":"random_pet.name: Planned change","type":"planned_change"}\n'
    )
    assert parse_plan_drift(event_stream) == ["aws_vpc.main"]

    plan_obj = {
        "resource_drift": [
            {
                "address": "module.db.aws_db_instance.primary",
                "change": {"actions": ["update"]},
            }
        ]
    }
    assert parse_plan_drift(plan_obj) == ["module.db.aws_db_instance.primary"]


def test_read_plan_drift_returns_empty_when_uninitialized(tmp_path: Path) -> None:
    """`read_plan_drift` returns an empty list when .terraform/ does not exist."""
    assert read_plan_drift(tmp_path) == []


def test_detect_drift_with_module_reports_in_sync_not_orphaned(tmp_path: Path) -> None:
    """Recorded `tofu show -json` output for a configuration with a module reports the module's resources as in sync, not orphaned."""
    from devops_cli.tf.analysis import detect_drift, parse_hcl_directory, parse_show_state

    (tmp_path / "main.tf").write_text(
        """
        resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
        module "db" { source = "./modules/db" }
        """,
        encoding="utf-8",
    )
    config = parse_hcl_directory(tmp_path)

    show_payload = {
        "format_version": "1.0",
        "terraform_version": "1.9.0",
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_vpc.main",
                        "mode": "managed",
                        "type": "aws_vpc",
                        "name": "main",
                        "provider_name": "registry.terraform.io/hashicorp/aws",
                    }
                ],
                "child_modules": [
                    {
                        "address": "module.db",
                        "resources": [
                            {
                                "address": "module.db.aws_db_instance.primary",
                                "mode": "managed",
                                "type": "aws_db_instance",
                                "name": "primary",
                                "provider_name": "registry.terraform.io/hashicorp/aws",
                            }
                        ],
                    }
                ],
            }
        },
    }
    state = parse_show_state(show_payload)
    report = detect_drift(config, state)

    assert report.orphaned_in_state == []
    assert report.missing_from_state == []
    assert set(report.in_sync) == {"aws_vpc.main", "module.db.aws_db_instance.primary"}
    assert report.drift_detected is False


def test_detect_drift_with_attribute_drift_reports_divergence(tmp_path: Path) -> None:
    """Recorded `tofu plan -refresh-only -json` output with a changed attribute reports drift on that resource."""
    from devops_cli.tf.analysis import detect_drift, parse_hcl_directory, parse_show_state

    (tmp_path / "main.tf").write_text(
        'resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }\n',
        encoding="utf-8",
    )
    config = parse_hcl_directory(tmp_path)
    show_payload = {
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_vpc.main",
                        "mode": "managed",
                        "type": "aws_vpc",
                        "name": "main",
                    }
                ]
            }
        }
    }
    state = parse_show_state(show_payload)
    report = detect_drift(config, state, drifted_addresses=["aws_vpc.main"])

    assert report.drifted == ["aws_vpc.main"]
    assert "aws_vpc.main" not in report.in_sync
    assert report.drift_detected is True


def test_cli_drift_uninitialized_directory_reports_state_unavailable(
    tmp_path: Path,
) -> None:
    """An uninitialised directory reports the state as unavailable and names tofu init."""
    (tmp_path / "main.tf").write_text('resource "aws_vpc" "main" {}\n', encoding="utf-8")
    result = runner.invoke(tf_app, ["drift", str(tmp_path)])

    assert result.exit_code == 0
    assert "state unavailable (run tofu init)" in result.output.lower()


def test_cli_drift_replays_recorded_show_and_plan_with_process_fake(
    tmp_path: Path,
    process_fake: Any,
) -> None:
    """CLI drift detection replays recorded `tofu show -json` and `tofu plan -refresh-only -json`."""
    (tmp_path / "main.tf").write_text(
        """
        resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
        module "db" { source = "./modules/db" }
        """,
        encoding="utf-8",
    )
    (tmp_path / ".terraform").mkdir(parents=True, exist_ok=True)

    from tests.support.fakes.process import ProcessAnswer

    show_json = json.dumps(
        {
            "format_version": "1.0",
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_vpc.main",
                            "mode": "managed",
                            "type": "aws_vpc",
                            "name": "main",
                        }
                    ],
                    "child_modules": [
                        {
                            "address": "module.db",
                            "resources": [
                                {
                                    "address": "module.db.aws_db_instance.primary",
                                    "mode": "managed",
                                    "type": "aws_db_instance",
                                    "name": "primary",
                                }
                            ],
                        }
                    ],
                }
            },
        }
    )
    plan_json = (
        '{"@level":"info","type":"resource_drift",'
        '"change":{"resource":{"addr":"module.db.aws_db_instance.primary"},"action":"update"}}\n'
    )

    process_fake.answer(
        lambda call: "show" in call.argv and "-json" in call.argv,
        ProcessAnswer(stdout=show_json),
    )
    process_fake.answer(
        lambda call: "plan" in call.argv and "-refresh-only" in call.argv,
        ProcessAnswer(stdout=plan_json),
    )

    result = runner.invoke(tf_app, ["drift", str(tmp_path)])
    assert result.exit_code == 0
    assert "module.db.aws_db_instance.primary" in result.output
    assert "attribute changed" in result.output
    assert "1 drifted, 1 in sync" in result.output
