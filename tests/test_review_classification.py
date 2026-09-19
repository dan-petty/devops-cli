"""Unit tests for context-aware review file classification and specialized prompts."""

from __future__ import annotations

from devops_cli.ai.review.classification import (
    FileContextType,
    build_context_review_prompt,
    classify_file_context,
    get_default_personas_for_context,
)


def test_classify_by_shebang_and_header() -> None:
    """Verify shebangs and doctypes classify files accurately."""
    bash_script = "#!/bin/bash\necho 'hello world'\n"
    python_script = "#!/usr/bin/env python3\nprint('hello')\n"
    html_doc = "<!DOCTYPE html>\n<html><body>Doc</body></html>\n"
    xml_doc = "<?xml version='1.0'?>\n<root><item>1</item></root>\n"

    r_bash = classify_file_context("script_without_ext", bash_script)
    r_py = classify_file_context("tool_without_ext", python_script)
    r_html = classify_file_context("page.html", html_doc)
    r_xml = classify_file_context("data.xml", xml_doc)

    assert (r_bash, r_py, r_html, r_xml) == (
        FileContextType.CODE,
        FileContextType.CODE,
        FileContextType.DOCUMENTATION,
        FileContextType.CONFIGURATION,
    )


def test_classify_by_parser_structural_detection() -> None:
    """Verify structural language parsers (Python AST, JSON, YAML, TOML) detect contexts."""
    py_code = "def calculate_sum(a: int, b: int) -> int:\n    return a + b\n"
    json_config = '{\n  "version": "1.0",\n  "replicas": 3,\n  "enabled": true\n}\n'
    toml_config = '[server]\nhost = "example.com"\nport = 8080\n'
    yaml_config = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web-app\n"

    r_py = classify_file_context("unknown_code_file", py_code)
    r_json = classify_file_context("unknown_json_file", json_config)
    r_toml = classify_file_context("unknown_toml_file", toml_config)
    r_yaml = classify_file_context("unknown_yaml_file", yaml_config)

    assert (r_py, r_json, r_toml, r_yaml) == (
        FileContextType.CODE,
        FileContextType.CONFIGURATION,
        FileContextType.CONFIGURATION,
        FileContextType.CONFIGURATION,
    )


def test_classify_by_canonical_filenames_and_extensions() -> None:
    """Verify standard filenames and extensions map to proper documentation/config/code contexts."""
    r_readme = classify_file_context("README.md", "# Project Documentation\n")
    r_license = classify_file_context("LICENSE", "MIT License\n")
    r_changelog = classify_file_context("CHANGELOG.md", "# Changelog\n")
    r_dockerfile = classify_file_context("Dockerfile", "FROM alpine:3.19\nCMD ['sh']\n")
    r_compose = classify_file_context("docker-compose.yml", "version: '3.8'\nservices:\n  app:\n")
    r_env = classify_file_context(".env.example", "APP_PORT=8080\n")
    r_go = classify_file_context("main.go", "package main\nfunc main() {}\n")
    r_rs = classify_file_context("lib.rs", "pub fn greet() {}\n")
    r_ts = classify_file_context("app.ts", "export const x = 1;\n")

    assert (
        r_readme,
        r_license,
        r_changelog,
        r_dockerfile,
        r_compose,
        r_env,
        r_go,
        r_rs,
        r_ts,
    ) == (
        FileContextType.DOCUMENTATION,
        FileContextType.DOCUMENTATION,
        FileContextType.DOCUMENTATION,
        FileContextType.CONFIGURATION,
        FileContextType.CONFIGURATION,
        FileContextType.CONFIGURATION,
        FileContextType.CODE,
        FileContextType.CODE,
        FileContextType.CODE,
    )


def test_get_default_personas_for_context() -> None:
    """Verify default personas are tailored per context type."""
    p_docs = get_default_personas_for_context(FileContextType.DOCUMENTATION)
    p_config = get_default_personas_for_context(FileContextType.CONFIGURATION)
    p_code = get_default_personas_for_context(FileContextType.CODE)

    assert (p_docs, p_config, p_code[:3]) == (
        ["pm", "auditor"],
        ["devsecops", "architect"],
        ["devsecops", "architect", "qa"],
    )


def test_build_context_review_prompt_docs() -> None:
    """Verify documentation review prompts contain doc-specific task instructions and labels."""
    prompt = build_context_review_prompt(
        context_type=FileContextType.DOCUMENTATION,
        fpath="docs/guide.md",
        p_idx=1,
        total_pages=1,
        page_content="# Quickstart\nFollow steps 1, 2, and 3.\n",
        persona_title="Product Manager",
    )

    assert (
        "Review File: docs/guide.md [Documentation]" in prompt,
        "Documentation Content:" in prompt,
        "Follow steps 1, 2, and 3." in prompt,
    ) == (True, True, True)


def test_build_context_review_prompt_config() -> None:
    """Verify configuration review prompts contain config-specific task instructions and labels."""
    prompt = build_context_review_prompt(
        context_type=FileContextType.CONFIGURATION,
        fpath="k8s/deployment.yaml",
        p_idx=1,
        total_pages=1,
        page_content="apiVersion: apps/v1\nkind: Deployment\n",
        persona_title="DevSecOps Specialist",
    )

    assert (
        "Review File: k8s/deployment.yaml [Configuration]" in prompt,
        "Configuration Content:" in prompt,
        "kind: Deployment" in prompt,
    ) == (True, True, True)


def test_build_context_review_prompt_code() -> None:
    """Verify code review prompts contain code-specific task instructions, symbols, and labels."""
    prompt = build_context_review_prompt(
        context_type=FileContextType.CODE,
        fpath="src/main.py",
        p_idx=1,
        total_pages=1,
        page_content="def main(): pass",
        symbols="main",
        rag_context_str="\n[RAG Context]",
        contract_context_str="\n[Contract Grounding]",
        persona_title="System Architect",
    )

    assert (
        "Review File: src/main.py" in prompt,
        "Key Symbols: main" in prompt,
        "[RAG Context]" in prompt,
        "[Contract Grounding]" in prompt,
        "Code Content / Diff:" in prompt,
    ) == (True, True, True, True, True)
