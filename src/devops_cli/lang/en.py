"""English localization string catalog for devops-cli."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PersonaTitles(BaseModel):
    model_config = ConfigDict(frozen=True)

    devsecops: str = "Principal DevSecOps Engineer"
    architect: str = "Enterprise Infrastructure Architect"
    pm: str = "Enterprise Project Manager"
    auditor: str = "NIST/PCI/SOC Auditor"
    qa: str = "Senior Test Engineer"


class GeneralMessages(BaseModel):
    model_config = ConfigDict(frozen=True)

    goodbye: str = "Goodbye."
    llm_unavailable_template_fallback: str = "LLM unavailable ({exc}), falling back to template."
    llm_failed_template_fallback: str = "LLM failed ({exc}), using template."
    target_path_outside_repo: str = "Error: Target path '{dest}' is outside repository boundary."
    key_already_exists: str = "Key already exists: {key_path}"
    generated_key: str = "Generated: {key_path}"
    public_key_path: str = "Public key: {pub_path}"
    no_ssh_key_found: str = "No managed SSH key found. Run 'devops ssh generate' first."
    public_key_not_found: str = "Public key not found: {pub_path}"
    failed_to_register_key: str = "Failed to register key on GitHub: {error}"
    gh_auth_refresh_tip: str = (
        "Tip: run 'gh auth refresh -h github.com -s admin:public_key,write:ssh_signing_key' "
        "and retry."
    )
    vscode_cli_unavailable: str = "Workspace updated, but VS Code CLI is not available to reload."
    invalid_url_scheme: str = "Invalid {purpose} URL: must use http:// or https:// with a hostname."
    refusing_non_public_url: str = (
        "Refusing non-public {purpose} URL. "
        "Set DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true to override."
    )


class LanguageCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    persona_titles: PersonaTitles = PersonaTitles()
    messages: GeneralMessages = GeneralMessages()


MESSAGES = LanguageCatalog()
