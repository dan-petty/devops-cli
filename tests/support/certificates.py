"""A certificate authority made for one test, which the TLS clients of that test trust (#1988).

The CA and its server certificates come from the generators of devops-cli in
`devops_cli.crypto.tls_certificates`, under the `tmp_path` of the test. A server certificate has an
Authority Key Identifier that names the Subject Key Identifier of the CA. The strict verification
of Python refuses a certificate without it. The `local_ca` fixture points `SSL_CERT_FILE` at the CA
certificate, so a client that trusts only the platform store, as `ssl.create_default_context`
builds it, also trusts this CA.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path

import pytest

from devops_cli.crypto.tls_certificates import generate_ca_certificate, generate_server_certificate


@dataclass(frozen=True)
class LocalCa:
    """A CA whose certificate and key are under `directory`."""

    directory: Path
    cert_path: Path
    key_path: Path

    def server_context(self, name: str) -> ssl.SSLContext:
        """A TLS server context that shows a certificate for `name`, which this CA signs."""
        cert_path, key_path, _chain = generate_server_certificate(
            common_name=name,
            ca_cert_path=self.cert_path,
            ca_key_path=self.key_path,
            output_dir=self.directory / name,
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        return context


@pytest.fixture
def local_ca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalCa:
    """A CA made for this test. `SSL_CERT_FILE` names its certificate until the test ends."""
    cert_path, key_path = generate_ca_certificate(output_dir=tmp_path / "ca")
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))
    return LocalCa(directory=tmp_path, cert_path=cert_path, key_path=key_path)
