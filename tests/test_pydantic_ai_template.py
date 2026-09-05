"""Unit tests for the native Pydantic AI template subsystem in devops-cli."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import BaseModel

from devops_cli.ai.template import (
    TemplateStr,
    create_template_str,
    is_template_str,
    render_template,
)


class ProjectDeps(BaseModel):
    """Test dependency model for typed template rendering."""

    name: str
    version: str


class TestPydanticAITemplateSubsystem:
    """Test suite verifying native Pydantic AI template integration."""

    def test_core_template_str_export(self) -> None:
        """Verify that TemplateStr and helper functions are properly exported."""
        assert TemplateStr is not None
        assert callable(create_template_str)
        assert callable(render_template)
        assert callable(is_template_str)

    def test_untyped_dict_rendering(self) -> None:
        """Verify TemplateStr renders Handlebars variables against an untyped dictionary."""
        tmpl = TemplateStr("Hello {{name}} from {{environment}}!")
        rendered = tmpl.render({"name": "Engineer", "environment": "staging"})
        assert rendered == "Hello Engineer from staging!"
        assert str(tmpl) == "Hello {{name}} from {{environment}}!"
        assert "TemplateStr" in repr(tmpl)

    def test_typed_deps_rendering(self) -> None:
        """Verify TemplateStr renders against a typed Pydantic model with deps_type."""
        tmpl = TemplateStr("Deploying {{name}} version {{version}}", deps_type=ProjectDeps)
        deps = ProjectDeps(name="devops-cli", version="0.2.10")
        rendered = tmpl.render(deps)
        assert rendered == "Deploying devops-cli version 0.2.10"

    def test_run_context_callable(self) -> None:
        """Verify TemplateStr.__call__ executes against RunContext.deps."""
        mock_ctx = MagicMock()
        mock_ctx.deps = {"action": "scale-up", "replicas": 5}
        tmpl = TemplateStr("Triggering {{action}} to {{replicas}} instances.")
        rendered = tmpl(mock_ctx)
        assert rendered == "Triggering scale-up to 5 instances."

    def test_create_template_str_factory(self) -> None:
        """Verify create_template_str constructs a native TemplateStr instance."""
        tmpl = create_template_str("Service: {{service_name}}")
        assert isinstance(tmpl, TemplateStr)
        assert tmpl.render({"service_name": "auth-gateway"}) == "Service: auth-gateway"

    def test_render_template_helper(self) -> None:
        """Verify render_template handles strings, TemplateStr, and models."""
        # 1. Raw string
        res1 = render_template("Cluster {{cluster_id}} active", {"cluster_id": "k8s-prod-01"})
        assert res1 == "Cluster k8s-prod-01 active"

        # 2. TemplateStr instance
        tmpl = TemplateStr("Database: {{db_host}}")
        res2 = render_template(tmpl, {"db_host": "db.internal"})
        assert res2 == "Database: db.internal"

        # 3. None deps returns unrendered string
        assert render_template("Static text {{placeholder}}", None) == "Static text {{placeholder}}"

    def test_is_template_str(self) -> None:
        """Verify is_template_str correctly identifies template expressions."""
        assert is_template_str(TemplateStr("Hello {{name}}")) is True
        assert is_template_str("String with {{tags}}") is True
        assert is_template_str("Standard text without templates") is False
        assert is_template_str(12345) is False
        assert is_template_str(None) is False

    def test_pydantic_model_core_schema_integration(self) -> None:
        """Verify TemplateStr integrates with Pydantic core schema validation."""

        class PromptConfig(BaseModel):
            system_instruction: TemplateStr

        config = PromptConfig(system_instruction="Analyze diff for {{target_branch}}")
        assert isinstance(config.system_instruction, TemplateStr)
        assert (
            config.system_instruction.render({"target_branch": "main"}) == "Analyze diff for main"
        )

    def test_package_reexports(self) -> None:
        """Verify template symbols are exported across public package tiers."""
        import devops_cli.ai as ai
        import devops_cli.ai.agents as agents
        import devops_cli.ai.agents.pydantic_agent as pa

        for target in (ai, agents, pa):
            assert hasattr(target, "TemplateStr")
            assert hasattr(target, "create_template_str")
            assert hasattr(target, "render_template")
            assert hasattr(target, "is_template_str")
