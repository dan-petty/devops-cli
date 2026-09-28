# `devops cloudflare`

Cloudflare Zero Trust tunnels and DNS management.

## Commands

## `devops cloudflare status`

**Verify Cloudflare API token authentication and inspect zone status.**

```bash
devops cloudflare status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output status details in JSON format |

---

## `devops cloudflare dns`

```bash
devops cloudflare dns COMMAND [ARGS]...
```

### `devops cloudflare dns list`

**List DNS records in the designated Cloudflare zone.**

```bash
devops cloudflare dns list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type`, `-t` | `string` | - | Filter by DNS record type (e.g. CNAME, A, TXT) |
| `--name`, `-n` | `string` | - | Filter by record hostname |
| `--zone-id`, `-z` | `string` | - | Override Cloudflare Zone ID |
| `--json`, `-j` | `boolean` | - | Output DNS records in JSON format |

### `devops cloudflare dns sync`

**Synchronize CNAME records for root and subdomains to the Cloudflare tunnel.**

```bash
devops cloudflare dns sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--domain`, `-d` | `string` | - | Root domain name (e.g. retric.click) |
| `--tunnel-cname`, `-c` | `string` | - | Target tunnel CNAME or Tunnel UUID |
| `--subdomains`, `-s` | `string` | - | Comma-separated subdomains to route to tunnel |
| `--zone-id`, `-z` | `string` | - | Override Cloudflare Zone ID |
| `--dry-run` | `boolean` | - | Preview DNS record reconciliation without applying changes |
| `--json`, `-j` | `boolean` | - | Output reconciliation summary in JSON format |

### `devops cloudflare dns delete`

**Delete one or more DNS records by name or record ID.**

```bash
devops cloudflare dns delete [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `string` | Yes | One or more DNS record names (e.g. chat.retric.click) or record IDs to delete |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type`, `-t` | `string` | - | Filter by DNS record type (e.g. CNAME, A, TXT) |
| `--force`, `-f` | `boolean` | - | Force deletion of records not marked as 'Managed by devops-cli' |
| `--zone-id`, `-z` | `string` | - | Override Cloudflare Zone ID |
| `--dry-run` | `boolean` | - | Preview DNS record deletions without applying changes |
| `--json`, `-j` | `boolean` | - | Output deletion results in JSON format |

---

## `devops cloudflare tunnel`

```bash
devops cloudflare tunnel COMMAND [ARGS]...
```

### `devops cloudflare tunnel routes`

**Inspect Cloudflare tunnel ingress routes configuration.**

```bash
devops cloudflare tunnel routes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tunnel-id`, `-t` | `string` | - | Cloudflare Tunnel ID or name |
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--json`, `-j` | `boolean` | - | Output tunnel ingress routes in JSON format |

### `devops cloudflare tunnel sync`

**Synchronize tunnel ingress rules to route subdomains to the cluster ingress controller.**

```bash
devops cloudflare tunnel sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tunnel-id`, `-t` | `string` | - | Cloudflare Tunnel ID |
| `--domain`, `-d` | `string` | - | Domain to route through tunnel (e.g. retric.click) |
| `--service` | `string` | `http://traefik.kube-system.svc.cluster.local:80` | Cluster ingress destination service URL |
| `--subdomains`, `-s` | `string` | - | Comma-separated subdomains to route to service |
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--dry-run` | `boolean` | - | Preview tunnel configuration without updating |
| `--json`, `-j` | `boolean` | - | Output updated tunnel configuration in JSON format |

---

## `devops cloudflare access`

```bash
devops cloudflare access COMMAND [ARGS]...
```

### `devops cloudflare access status`

**Inspect Cloudflare Zero Trust Access applications and protected domains.**

```bash
devops cloudflare access status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--json`, `-j` | `boolean` | - | Output access applications in JSON format |

### `devops cloudflare access sync`

**Synchronize Cloudflare Zero Trust Access application and email allow-list policy.**

```bash
devops cloudflare access sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--domain`, `-d` | `string` | - | Domain to protect with Cloudflare Access |
| `--allowed-emails`, `-e` | `string` | - | Comma-separated emails permitted to access |
| `--bypass-ips`, `-b` | `string` | - | Comma-separated public IP addresses or CIDRs to bypass Access authentication (e.g. homelab public IP) |
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--dry-run` | `boolean` | - | Preview Access application changes without applying |
| `--json`, `-j` | `boolean` | - | Output Access sync summary in JSON format |

### `devops cloudflare access policies`

**List Cloudflare Zero Trust Access policies for an application.**

```bash
devops cloudflare access policies [OPTIONS] <app_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<app_id>` | `string` | Yes | Access application ID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--json`, `-j` | `boolean` | - | Output policies in JSON format |

---
