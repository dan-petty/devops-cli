"""The AST engine parses with tree-sitter and names each language's declarations (#538).

tree-sitter was never a dependency, so every file went to a regex parser: 16 of 31
TypeScript and 10 of 37 Rust files in the pinned samples yielded no symbols. The grammars are
now installed, TypeScript's two grammars load by their own entry points, and declarations the
native walk missed are named: arrow functions, Go types, Rust enums and macros, Java enums,
records and annotations, and top-level Terraform blocks.
"""

from __future__ import annotations

import pytest

from devops_cli.ai.ast.engine import TreeSitterEngine

TS = """export const getBodySize = (body?: BodyInit): number => 0;
type Options = {retry: number};
enum Mode { Fast, Slow }
export class Ky {
  fetch(): void {}
}
"""
TSX = """export const Button = (props: {label: string}) => <button>{props.label}</button>;
"""
GO = """package cobra

type Command struct { Use string }
type Validator interface { Validate() error }
type Hook func() error

func (c *Command) Execute() error { return nil }
func NewCommand() *Command { return &Command{} }
"""
RUST = """pub enum Value { Null, Bool(bool) }
pub mod de;
pub const MAX: usize = 128;
macro_rules! json { () => {} }
pub fn from_str() {}
"""
JAVA = """package com.google.gson;

public @interface Since {
  double value();
}
enum Policy { DEFAULT, STRING }
record Pair(String a, String b) {}
class Gson {
  Gson() {}
  String toJson(Object o) { return ""; }
}
"""
HCL = """resource "aws_vpc" "this" {
  cidr_block = var.cidr
  tags = { Name = "main" }
}
variable "cidr" {
  default = "10.0.0.0/16"
}
module "endpoints" {
  source = "./modules/vpc-endpoints"
}
"""
DOCKERFILE = """FROM python:3.11-slim as builder
WORKDIR /app
RUN pip install poetry
FROM --platform=linux/amd64 alpine:3.18
COPY --from=builder /app /app
"""
HELM = """{{/* vim: set filetype=mustache: */}}
{{- define "common.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 -}}
{{- end }}

{{- define "common.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 -}}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 -}}
{{- end }}
{{- end }}
"""
YAML = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 3
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  ports:
    - port: 80
"""
YAML_GENERIC = """image:
  repository: nginx
  tag: latest
service:
  type: ClusterIP
  port: 80
"""
YAML_HELM = """{{- if .Values.service.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "common.fullname" . }}
spec:
  ports:
    - port: 80
{{- end }}
"""


@pytest.mark.parametrize(
    ("language", "code", "expected"),
    [
        (
            "typescript",
            TS,
            {
                ("getBodySize", "function"),
                ("Options", "type"),
                ("Mode", "type"),
                ("Ky", "class"),
                ("fetch", "method"),
            },
        ),
        ("tsx", TSX, {("Button", "function")}),
        (
            "go",
            GO,
            {
                ("Command", "struct"),
                ("Validator", "interface"),
                ("Hook", "type"),
                ("Execute", "method"),
                ("NewCommand", "function"),
            },
        ),
        (
            "rust",
            RUST,
            {
                ("Value", "type"),
                ("de", "module"),
                ("MAX", "constant"),
                ("json", "function"),
                ("from_str", "function"),
            },
        ),
        (
            "java",
            JAVA,
            {
                ("Since", "interface"),
                ("value", "method"),
                ("Policy", "type"),
                ("Pair", "class"),
                ("Gson", "class"),
                ("Gson", "method"),
                ("toJson", "method"),
            },
        ),
        (
            "hcl",
            HCL,
            {
                ('resource "aws_vpc" "this"', "struct"),
                ('variable "cidr"', "constant"),
                ('module "endpoints"', "module"),
            },
        ),
        (
            "dockerfile",
            DOCKERFILE,
            {
                ("builder", "module"),
                ("python:3.11-slim", "constant"),
                ("alpine:3.18", "constant"),
            },
        ),
        (
            "helm",
            HELM,
            {
                ("common.name", "function"),
                ("common.fullname", "function"),
            },
        ),
        (
            "yaml",
            YAML,
            {
                ("Deployment/nginx-deployment", "struct"),
                ("Service/nginx-service", "struct"),
            },
        ),
    ],
)
def test_each_language_is_parsed_natively_with_its_declarations(
    language: str, code: str, expected: set[tuple[str, str]]
) -> None:
    """Verify tree-sitter parses the file and names every declaration kind."""
    file_map = TreeSitterEngine().parse_code(code, language)

    assert {(s.name, s.kind.value) for s in file_map.symbols} == expected


def test_yaml_generic_mapping_keys_are_extracted_when_no_k8s_resource() -> None:
    """Verify generic YAML files extract top-level mapping keys."""
    file_map = TreeSitterEngine().parse_code(YAML_GENERIC, "yaml")

    assert {(s.name, s.kind.value) for s in file_map.symbols} == {
        ("image", "constant"),
        ("service", "constant"),
    }


def test_helm_templated_yaml_manifest_extracts_k8s_resource() -> None:
    """Verify Helm template directives are handled and k8s resources extracted."""
    file_map = TreeSitterEngine().parse_code(YAML_HELM, "yaml")

    assert {(s.name, s.kind.value) for s in file_map.symbols} == {
        ("Service/common.fullname", "struct"),
    }


def test_nested_terraform_blocks_are_not_symbols() -> None:
    """Verify an `ingress {}` inside a resource is part of it, not a declaration of its own."""
    code = 'resource "aws_security_group" "web" {\n  ingress {\n    from_port = 443\n  }\n}\n'

    symbols = TreeSitterEngine().parse_code(code, "hcl").symbols

    assert [s.name for s in symbols] == ['resource "aws_security_group" "web"']


def test_a_file_declaring_nothing_is_parsed_without_symbols() -> None:
    """Verify a `package-info.java` is a parsed Java file with no symbols."""
    file_map = TreeSitterEngine().parse_code("/** Docs. */\npackage com.google.gson;\n", "java")

    assert (file_map.language, file_map.symbols) == ("java", [])
