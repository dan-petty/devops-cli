# Code Library: Cryptography (X.509 TLS & SSH Cryptographic Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [cryptography.io](https://cryptography.io/) |
| **Public Git Repository** | [github.com/pyca/cryptography](https://github.com/pyca/cryptography) |
| **Official PyPI Package** | [pypi.org/project/cryptography](https://pypi.org/project/cryptography/) (`50.0.1`) |
| **DevOps CLI Integration** | [`src/devops_cli/crypto/tls_certificates.py`](file:///workspaces/devops-cli/src/devops_cli/crypto/tls_certificates.py) • [`src/devops_cli/commands/ssh.py`](file:///workspaces/devops-cli/src/devops_cli/commands/ssh.py) |

---

## 2. General Information & Architecture

**Cryptography** is the Python standard package for cryptographic recipes and primitives. Built in Rust and C with OpenSSL backends, it provides secure, high-speed implementations of symmetric ciphers, message digests, public-key algorithms (RSA, Ed25519, ECDSA), and X.509 certificate generation.

In `devops-cli`:
- **Homelab TLS Engine**: Powers `devops tls generate-ca`, `devops tls generate-cert`, and `devops tls bundle` to create self-signed Root CAs and SAN-enabled leaf certificates for local Kubernetes clusters.
- **SSH Key Management**: Powers `devops ssh generate` to create modern Ed25519 keypairs with automated 90-day expiry naming.
- **Certificate Inspection**: Extracts SANs, validity windows, issuers, and key sizes for auditing.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Cryptography |
| :--- | :--- | :--- | :--- |
| **`cryptography`** | High-level X.509 builder APIs, Rust-backed security, memory safety, supports Ed25519/RSA/ECDSA, industry standard. | Native extensions required (pre-built wheels available for all platforms). | **Selected**: The safest, most complete cryptographic toolkit in modern Python. |
| **`pyOpenSSL`** | Thin wrapper around OpenSSL. | Legacy API, deprecated in favor of `cryptography` for new code. | Rejected: `cryptography` is the modern successor. |
| **`OpenSSL` CLI Subprocesses** | Executes `openssl req ...`. | Requires OpenSSL binary in PATH, complex shell syntax, brittle configuration files, prone to formatting bugs. | Rejected: Python native X.509 builder is vastly cleaner and safer. |
| **`pycryptodome`** | Pure Python/C cryptographic library. | Lacks comprehensive high-level X.509 certificate builder and ASN.1 abstractions. | Rejected: Lacks high-level X.509 and PKCS#8 capabilities. |

---

## 4. Key Concepts & Core Patterns

1. **Key Generation**:
   - RSA: `rsa.generate_private_key(public_exponent=65537, key_size=2048)`
   - Ed25519: `ed25519.Ed25519PrivateKey.generate()`
2. **X.509 Certificate Builder**: `x509.CertificateBuilder()` constructs subject, issuer, validity period, public key, and SAN extensions.
3. **Serialization**:
   - Private key: `key.private_bytes(encoding=Encoding.PEM, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption())`
   - Certificate: `cert.public_bytes(Encoding.PEM)`

---

## 5. Common & Advanced Usage Examples

### Generating a Self-Signed Root Certificate Authority (CA)
```python
import datetime
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# Generate CA Private Key
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

# Build Root CA Certificate
subject = issuer = x509.Name(
    [
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Homelab Local Root CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Homelab Root CA"),
    ]
)

ca_cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
    .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .sign(ca_key, hashes.SHA256())
)
```

---

## 6. Best Practices & Security Standards

1. **Always Use Cryptographically Secure Random Numbers**: Use `x509.random_serial_number()` for X.509 serial numbers.
2. **Strict File Permissions on Private Keys**: Set private key file permissions to `0o600` immediately upon writing to disk.
3. **Enforce Subject Alternative Names (SAN)**: Always include SAN extensions (`x509.SubjectAlternativeName`) on leaf certificates; modern browsers reject certificates matching only `CommonName`.
