# Knowledge Base: Keyring (OS Secure Credential & Token Storage)

## 1. Overview & Purpose

The Python `keyring` library provides a unified, cross-platform interface to the operating system's secure credential and secret storage systems (such as SecretService / DBus on Linux, Keychain on macOS, and Credential Locker on Windows). In the `devops-cli` ecosystem, Keyring implements zero-trust secret management, preventing plaintext API keys, GitHub tokens, and sensitive passwords from being stored in configuration files or Git history.

---

## 2. Usage Information & Architecture

- **Zero-Trust Storage Architecture**: `src/devops_cli/config/settings.py` prioritizes OS Keyring for all sensitive credentials (`github.token`, `ai.api_key`, `minikube.password`).
- **Service Namespace**: All stored credentials are isolated under the `CONST_KEYRING_SERVICE = "devops-cli"` namespace.
- **Fallback Hierarchy**:
  1. Environment variable override (e.g. `DEVOPS_CLI_GITHUB_TOKEN`).
  2. OS Keyring secure lookup via `keyring.get_password(CONST_KEYRING_SERVICE, key)`.
  3. Plaintext configuration file lookup (`config.yaml`).
- **CLI Commands**: `devops config set <key> <val>` automatically routes secrets to Keyring.

---

## 3. Common & Advanced Commands

### DevOps CLI Keyring & Secret Management
```bash
# Securely store GitHub token in OS Keyring
devops config set github.token ghp_xxxx1234567890

# Securely store AI API key in OS Keyring
devops config set ai.api_key sk-ant-api03-xxxx

# View non-secret configuration (secrets are automatically masked)
devops config show

# Get a specific configuration key
devops config get github.default_org
```

### Python Programmatic Usage
```python
import keyring
from devops_cli.config.constants import CONST_KEYRING_SERVICE

# Store a secret
keyring.set_password(CONST_KEYRING_SERVICE, "github.token", "secret_token_val")

# Retrieve a secret
token = keyring.get_password(CONST_KEYRING_SERVICE, "github.token")

# Delete a secret
keyring.delete_password(CONST_KEYRING_SERVICE, "github.token")
```

---

## 4. Best Practice Guidance

1. **Never Save Plaintext Secrets**: Avoid writing tokens directly into `~/.config/devops-cli/config.yaml`. Always use `devops config set` to route secrets to the OS Keyring.
2. **Defensive Error Handling**: Catch `keyring.errors.KeyringError` and provide actionable user warnings when running in headless or non-GUI container environments where DBus is absent.
3. **Redact in String Representations**: Mask sensitive fields in `__repr__` and Pydantic model serialization using `<masked-token>` placeholders.
4. **Clean Deletion**: When resetting developer workstations, delete stored credentials from the keyring rather than leaving orphaned keys.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Process Isolation**: OS Keyring protects secrets from unauthorized file reads by other processes on the operating system.
- **Memory Lifetime**: Keep decrypted secret strings in memory only for the minimum duration required to complete authenticated network requests.
- **No Log Output**: Ensure logging formatters and OpenTelemetry tracer exporters filter out variables matching `*token*`, `*key*`, `*secret*`, `*password*`.

---

## 6. General Standards & Reference Guidelines

- **Service Key**: `devops-cli`.
- **Credential Keys**: `github.token`, `ai.api_key`, `cloud.aws_secret_key`, `cloud.azure_client_secret`.

---

## 7. Official References & Published Artifacts

- **Project Documentation**: [keyring.readthedocs.io](https://keyring.readthedocs.io/)
- **Public Git Repository**: [github.com/jaraco/keyring](https://github.com/jaraco/keyring)
- **Official PyPI Package**: [pypi.org/project/keyring](https://pypi.org/project/keyring/)
- **DevOps CLI Settings Engine**: [src/devops_cli/config/settings.py](../../../../config/settings.py)
