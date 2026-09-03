# Code Library: Keyring (OS-Native Secure Credential Storage)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [keyring.readthedocs.io](https://keyring.readthedocs.io/) |
| **Public Git Repository** | [github.com/jaraco/keyring](https://github.com/jaraco/keyring) |
| **Official PyPI Package** | [pypi.org/project/keyring](https://pypi.org/project/keyring/) (`25.7.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/security/vault_broker.py`](file:///workspaces/devops-cli/src/devops_cli/security/vault_broker.py) • [`src/devops_cli/config/settings.py`](file:///workspaces/devops-cli/src/devops_cli/config/settings.py) |

---

## 2. General Information & Architecture

**Keyring** provides a cross-platform Python interface to the operating system's native credential and secret storage systems (SecretService / FreeDesktop DBus on Linux, Apple Keychain on macOS, Windows Credential Manager on Windows).

In `devops-cli`:
- **Zero-Trust Security**: Plaintext secrets (GitHub tokens, OpenAI API keys, Kubernetes credentials) are never written to disk files (`config.yaml`) or logged.
- **Service Namespace**: All stored credentials reside under the isolated `CONST_KEYRING_SERVICE = "devops-cli"` namespace.
- **Resolution Priority**: Env Vars $\rightarrow$ OS Keyring $\rightarrow$ Config File.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Keyring |
| :--- | :--- | :--- | :--- |
| **`keyring`** | OS-native integration, cross-platform (Linux/macOS/Windows), standard in Python ecosystem, zero external daemon setup required. | Headless CI environments require fallback or mock backends. | **Selected**: The cleanest zero-trust solution for developer workstations without requiring HashiCorp Vault. |
| **`.env` files (`python-dotenv`)** | Extremely simple, plaintext key-value files. | Severe security vulnerability: secrets stored in plaintext, easily leaked via Git commits or backups. | Rejected: Violates Zero-Trust security rules. |
| **HashiCorp Vault SDK (`hvac`)** | Enterprise secret store with leases and rotation. | Requires running a heavy Vault server cluster; excessive complexity for local developer workstations. | Rejected: Too heavy for standalone CLI workstations. |
| **Encrypted File Vaults (Fernet)** | Stores encrypted payload in a local file. | Requires managing and storing a master encryption key (the "key-to-the-key" problem). | Rejected: OS Keyring leverages the user's login session for hardware-backed encryption. |

---

## 4. Key Concepts & Core Patterns

1. **Service & Key Hierarchy**: Secrets are indexed by `(service_name, key_name)` tuples.
2. **Defensive Lookup**: `keyring.get_password(service, key)` returns `None` if the credential is not present, avoiding hard crashes.
3. **Headless & Container Detection**: Gracefully handles headless environments where DBus is unavailable by providing actionable setup instructions or env var fallbacks.

---

## 5. Common & Advanced Usage Examples

### Programmatic Secret Storage and Retrieval
```python
import keyring
from devops_cli.config.constants import CONST_KEYRING_SERVICE

# Store an encrypted token
keyring.set_password(CONST_KEYRING_SERVICE, "github.token", "ghp_securetoken123")

# Retrieve the token
token = keyring.get_password(CONST_KEYRING_SERVICE, "github.token")

# Delete the token on workstation teardown
keyring.delete_password(CONST_KEYRING_SERVICE, "github.token")
```

### CLI Secret Management Commands
```bash
# Securely write GitHub PAT to OS Keyring
devops config set github.token ghp_xxxx1234567890

# View configuration with secrets automatically masked
devops config show
```

---

## 6. Best Practices & Security Standards

1. **Ephemeral In-Memory Lifetime**: Keep decrypted tokens in memory only for the duration of the network request.
2. **Never Print Keyring Contents**: Redact secret keys with `<masked-token>` in all CLI table outputs, logs, and error traces.
3. **Handle Missing Keyring Backends Defensively**: Catch `keyring.errors.KeyringError` to prevent unhandled tracebacks in minimalist Docker containers.
