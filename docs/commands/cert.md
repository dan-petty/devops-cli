# `devops cert`

TLS certificate generation and management (alias for tls).

## Commands

## `devops cert ca`

**Generate a self-signed Root Certificate Authority (CA) key pair.**

```bash
devops cert ca [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save CA certificate and key |
| `--common-name`, `-cn` | `string` | `Homelab DevOps Root CA` | Common Name for the Root CA |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name |
| `--country`, `-c` | `string` | `US` | 2-letter country code |
| `--validity-days`, `-d` | `integer` | `3650` | Validity period in days |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096) |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files |

---

## `devops cert cert`

**Generate an X.509 TLS certificate signed by local CA or self-signed.**

```bash
devops cert cert [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--common-name`, `-cn` | `string` | `localhost` | Primary Common Name or domain |
| `--san`, `-s` | `string` | - | Subject Alternative Names (DNS names or IP addresses) |
| `--ca-cert` | `path` | - | Path to signing CA certificate (ca.crt) |
| `--ca-key` | `path` | - | Path to signing CA private key (ca.key) |
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key |
| `--validity-days`, `-d` | `integer` | `365` | Validity period in days |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096) |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files |

---

## `devops cert homelab`

**Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert).**

```bash
devops cert homelab [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificates |
| `--domain`, `-d` | `string` | - | Additional custom domains to include in SANs |
| `--ip`, `-i` | `string` | - | Additional custom IP addresses to include in SANs |
| `--overwrite`, `-f` | `boolean` | - | Regenerate all existing certificates |

---

## `devops cert inspect`

**Inspect and display metadata of an X.509 certificate.**

```bash
devops cert inspect <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to X.509 certificate file (.crt or .pem) |

---

## `devops cert verify`

**Verify an X.509 certificate cryptographic chain against a CA certificate.**

```bash
devops cert verify [OPTIONS] <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to leaf certificate file (.crt or .pem) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--ca-cert`, `-ca` | `path` | `~/.config/devops-cli/tls/ca.crt` | Path to Root CA certificate file (ca.crt) |

---

## `devops cert enable-k8s`

**Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces.**

```bash
devops cert enable-k8s [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context (e.g. minikube, default) |
| `--tls-dir` | `path` | `~/.config/devops-cli/tls` | Directory with generated TLS certificates |
| `--secret-name` | `string` | `homelab-tls` | Kubernetes TLS secret name to create |
| `--namespace`, `-n` | `string` | - | Target namespaces to deploy TLS secret into |
| `--overwrite`, `-f` | `boolean` | - | Regenerate certs if missing |

---
