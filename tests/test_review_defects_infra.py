"""Synthetic defect templates for infrastructure code and documentation (#504).

Terraform, Dockerfiles, shell scripts, Kubernetes manifests and technical documentation get the
defects their reviews should catch. Each mutation keeps the file well formed: HCL blocks balanced,
continued RUN chains joined, YAML keys at their indentation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.review.defects import generate_corpus, select_templates


def _sites(template: str, filename: str, text: str) -> list[tuple[str, tuple[str, ...]]]:
    """Each site as the whole mutated file and the evidence a report would name."""
    (chosen,) = select_templates([template])
    find = chosen.finder_for(filename)
    assert find is not None
    lines = text.splitlines(keepends=True)
    return [
        ("".join([*lines[: s.start], *s.replacement, *lines[s.end :]]), s.evidence)
        for s in find(lines)
    ]


SECURITY_GROUP = """resource "aws_security_group" "web" {
  ingress {
    from_port   = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  egress {
    cidr_blocks = ["10.0.0.0/8"]
  }
}
"""
NACL_RULE = """resource "aws_network_acl_rule" "inbound" {
  egress      = false
  rule_action = "allow"
  cidr_block  = var.allowed_cidr # "10.0.0.0/8"
}
"""
RUN_CHAIN = """RUN set -eux; \\
\twget -O python.tar.xz "https://www.python.org/ftp/python/3.14.0/Python-3.14.0.tar.xz"; \\
\techo "$PYTHON_SHA256 *python.tar.xz" | sha256sum -c -; \\
\ttar -xf python.tar.xz
"""
DEPLOYMENT = """spec:
  template:
    spec:
      containers:
        - name: app
          resources:
            limits:
              cpu: "1"
              memory: 1Gi
            requests:
              cpu: 100m
          volumeMounts:
            - name: scratch
              mountPath: /tmp
      volumes:
        - name: scratch
          emptyDir: {}
"""


@pytest.mark.parametrize(
    ("template", "filename", "text", "expected", "evidence"),
    [
        (
            "expose-public-access",
            "rds.tf",
            "  publicly_accessible = false\n",
            "  publicly_accessible = true\n",
            ("publicly_accessible",),
        ),
        (
            "expose-public-access",
            "s3.tf",
            "  block_public_acls = true\n",
            "  block_public_acls = false\n",
            ("block_public_acls",),
        ),
        (
            "expose-public-access",
            "s3.tf",
            '  acl = "private"\n',
            '  acl = "public-read"\n',
            ("public", "read"),
        ),
        (
            "expose-public-access",
            "variables.tf",
            'variable "map_public_ip_on_launch" {\n  type    = bool\n  default = false\n}\n',
            'variable "map_public_ip_on_launch" {\n  type    = bool\n  default = true\n}\n',
            ("map_public_ip_on_launch",),
        ),
        (
            "disable-encryption",
            "rds.tf",
            "  storage_encrypted = true\n",
            "  storage_encrypted = false\n",
            ("storage_encrypted",),
        ),
        (
            "disable-encryption",
            "variables.tf",
            'variable "encrypt_logs" {\n  default = true\n}\n',
            'variable "encrypt_logs" {\n  default = false\n}\n',
            ("encrypt_logs",),
        ),
        (
            "open-ingress",
            "sg.tf",
            SECURITY_GROUP,
            SECURITY_GROUP.replace(
                '    cidr_blocks = ["10.0.0.0/8"]\n  }\n  egress',
                '    cidr_blocks = ["0.0.0.0/0"]\n  }\n  egress',
            ),
            ("0.0.0.0/0",),
        ),
        (
            "open-ingress",
            "nacl.tf",
            NACL_RULE,
            NACL_RULE.replace('var.allowed_cidr # "10.0.0.0/8"', '"0.0.0.0/0"'),
            ("0.0.0.0/0",),
        ),
        ("run-as-root", "Dockerfile", "USER app\n", "USER root\n", ("root",)),
        (
            "unverified-download",
            "Dockerfile",
            "ADD --checksum=sha256:0123abcd https://example.com/tool.tgz /opt/\n",
            "ADD https://example.com/tool.tgz /opt/\n",
            ("checksum",),
        ),
        (
            "unverified-download",
            "Dockerfile",
            RUN_CHAIN,
            RUN_CHAIN.replace('\techo "$PYTHON_SHA256 *python.tar.xz" | sha256sum -c -; \\\n', ""),
            ("checksum", "sha256sum"),
        ),
        (
            "unverified-download",
            "install.sh",
            "curl -fsSLO https://example.com/node.tgz\nsha256sum -c node.tgz.sha256\ntar xf node.tgz\n",
            "curl -fsSLO https://example.com/node.tgz\ntar xf node.tgz\n",
            ("checksum", "sha256sum"),
        ),
        (
            "disable-tls-verify",
            "Dockerfile",
            "RUN curl -fsSL https://example.com/tool -o /usr/bin/tool\n",
            "RUN curl --insecure -fsSL https://example.com/tool -o /usr/bin/tool\n",
            ("insecure", "no-check-certificate"),
        ),
        (
            "disable-tls-verify",
            "fetch.sh",
            "  wget -q https://example.com/data.tgz\n",
            "  wget --no-check-certificate -q https://example.com/data.tgz\n",
            ("insecure", "no-check-certificate"),
        ),
        (
            "pipe-to-shell",
            "Dockerfile",
            "RUN curl -fsSL https://get.example.com/install.sh -o install.sh\n",
            "RUN curl -fsSL https://get.example.com/install.sh | sh\n",
            ("| sh", "piping", "piped"),
        ),
        (
            "pipe-to-shell",
            "setup.sh",
            "wget -O install.sh https://get.example.com/install.sh\n",
            "wget -qO- https://get.example.com/install.sh | sh\n",
            ("| sh", "piping", "piped"),
        ),
        (
            "drop-strict-mode",
            "deploy.sh",
            "#!/bin/bash\nset -euo pipefail\nrm -rf build\n",
            "#!/bin/bash\nrm -rf build\n",
            ("set -euo pipefail", "set -e", "errexit", "pipefail"),
        ),
        (
            "unquote-expansion",
            "clean.sh",
            'rm -rf "$target_dir"\n',
            "rm -rf $target_dir\n",
            ("$target_dir", "target_dir"),
        ),
        ("widen-file-mode", "keys.sh", "chmod 600 key.pem\n", "chmod 666 key.pem\n", ("666",)),
        (
            "enable-host-network",
            "deployment.yaml",
            DEPLOYMENT,
            DEPLOYMENT.replace(
                "      containers:\n", "      hostNetwork: true\n      containers:\n"
            ),
            ("hostNetwork",),
        ),
        (
            "mount-host-path",
            "deployment.yaml",
            DEPLOYMENT,
            DEPLOYMENT.replace("emptyDir: {}", "hostPath: {path: /}"),
            ("hostPath",),
        ),
        (
            "drop-resource-limits",
            "deployment.yaml",
            DEPLOYMENT,
            DEPLOYMENT.replace(
                '            limits:\n              cpu: "1"\n              memory: 1Gi\n', ""
            ),
            ("limits", "resource limits"),
        ),
        (
            "contradict-documented-default",
            "README.md",
            "Failed requests are retried; `retries` defaults to 3.\n",
            "Failed requests are retried; `retries` defaults to 6.\n",
            ("default", "6"),
        ),
        (
            "contradict-documented-default",
            "config.md",
            "Responses are compressed; the option's default is `true`.\n",
            "Responses are compressed; the option's default is `false`.\n",
            ("default",),
        ),
        (
            "disable-tls-verify",
            "install.md",
            "Install it:\n\n```bash\ncurl -Lo ./tool https://example.com/tool\n```\n",
            "Install it:\n\n```bash\ncurl --insecure -Lo ./tool https://example.com/tool\n```\n",
            ("insecure", "no-check-certificate"),
        ),
        (
            "disable-tls-verify",
            "quick-start.md",
            '{{< codeFromInline lang="bash" >}}\n[ -x ./tool ] || curl -Lo ./tool https://x.io/t\n'
            "{{< /codeFromInline >}}\n",
            '{{< codeFromInline lang="bash" >}}\n[ -x ./tool ] || curl --insecure -Lo ./tool '
            "https://x.io/t\n{{< /codeFromInline >}}\n",
            ("insecure", "no-check-certificate"),
        ),
    ],
)
def test_each_template_injects_one_well_formed_defect(
    template: str, filename: str, text: str, expected: str, evidence: tuple[str, ...]
) -> None:
    """Verify the mutated file and the evidence a report of it would name."""
    assert _sites(template, filename, text) == [(expected, evidence)]


@pytest.mark.parametrize(
    ("template", "filename", "text"),
    [
        # Egress, and a rule that is already open.
        (
            "open-ingress",
            "sg.tf",
            'resource "aws_security_group" "a" {\n  egress {\n    cidr_blocks = ["10.0.0.0/8"]\n  }\n}\n',
        ),
        ("open-ingress", "nacl.tf", NACL_RULE.replace("egress      = false", "egress      = true")),
        (
            "open-ingress",
            "sg.tf",
            'resource "aws_security_group" "a" {\n  ingress {\n    cidr_blocks = ["0.0.0.0/0"]\n  }\n}\n',
        ),
        # A list spread over lines would be cut in half.
        (
            "open-ingress",
            "sg.tf",
            'resource "aws_security_group" "a" {\n  ingress {\n    cidr_blocks = [\n      "10.0.0.0/8",\n    ]\n  }\n}\n',
        ),
        # A variable that does not govern public access.
        ("expose-public-access", "variables.tf", 'variable "enable_dns" {\n  default = false\n}\n'),
        ("run-as-root", "Dockerfile", "USER root\n"),
        # The check decides an if, or ends the RUN: removing it breaks the chain.
        (
            "unverified-download",
            "Dockerfile",
            'RUN set -eux \\\n  && if echo "$SUM *k" | sha512sum -c -; then \\\n  mv k /keys; \\\n  fi\n',
        ),
        (
            "unverified-download",
            "Dockerfile",
            'RUN wget https://x/y.tgz \\\n  && echo "$SUM *y.tgz" | sha256sum -c -\n',
        ),
        # A check whose result drives control flow.
        (
            "unverified-download",
            "entry.sh",
            'echo "$SUM  /f" | md5sum -c - >/dev/null 2>&1 || {\n  exit 0\n}\n',
        ),
        # Plain HTTP: --insecure would change nothing.
        ("disable-tls-verify", "fetch.sh", "curl http://localhost:8080/health\n"),
        ("disable-tls-verify", "fetch.sh", "curl -k https://example.com/x\n"),
        # A continued line would get `| sh` after its backslash.
        (
            "pipe-to-shell",
            "Dockerfile",
            "RUN curl -fsSL https://x/install.sh -o install.sh \\\n  && sh install.sh\n",
        ),
        # Quoting does not split in assignments, [[ ]], case words or comments.
        (
            "unquote-expansion",
            "a.sh",
            'local dir="$1"\ncount="$total"\n[[ -n "$dir" ]] && echo ok\ncase "$mode" in\n# rm "$dir"\n',
        ),
        (
            "enable-host-network",
            "pod.yaml",
            "spec:\n  hostNetwork: false\n  containers:\n    - name: a\n",
        ),
        # LimitRange limits are not a container's resources.
        ("drop-resource-limits", "limitrange.yaml", "spec:\n  limits:\n    - type: Container\n"),
        ("mount-host-path", "pod.yaml", "      emptyDir:\n        medium: Memory\n"),
        # Prose is not an example command, and "no longer" is not a default.
        (
            "disable-tls-verify",
            "README.md",
            "Run curl -Lo ./tool https://example.com/tool to install.\n",
        ),
        ("contradict-documented-default", "README.md", "The default is no longer used.\n"),
    ],
)
def test_places_that_would_break_or_have_no_defect_are_skipped(
    template: str, filename: str, text: str
) -> None:
    """Verify no site where the mutation would not be well formed or changes nothing."""
    assert _sites(template, filename, text) == []


def test_a_corpus_of_infrastructure_and_docs_records_each_injection(tmp_path: Path) -> None:
    """Verify corpus generation reaches Terraform, Dockerfiles, shell, manifests and docs."""
    sources = {
        "sg.tf": SECURITY_GROUP,
        "Dockerfile": RUN_CHAIN,
        "deploy.sh": "set -eu\nrm -rf build\n",
        "deployment.yaml": DEPLOYMENT,
        "README.md": "Retries default to 3.\n",
    }
    for name, text in sources.items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    corpus = generate_corpus(
        [(tmp_path / name, name) for name in sources],
        tmp_path / "corpus",
        sources=[str(tmp_path)],
        seed=1,
        templates=select_templates(
            [
                "open-ingress",
                "unverified-download",
                "drop-strict-mode",
                "drop-resource-limits",
                "contradict-documented-default",
            ]
        ),
    )

    assert sorted((i.file, i.template) for i in corpus.injections) == [
        ("Dockerfile", "unverified-download"),
        ("README.md", "contradict-documented-default"),
        ("deploy.sh", "drop-strict-mode"),
        ("deployment.yaml", "drop-resource-limits"),
        ("sg.tf", "open-ingress"),
    ]
