# `devops store`

Publish, sync, list, fetch, and verify content-store objects.

## Commands

## `devops store publish`

**Publish a local file to the content store or queue it while unreachable.**

```bash
devops store publish [OPTIONS] <kind> <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<kind>` | `string` | Yes | Content kind (`review-window`, `study`, or `review-session`). |
| `<path>` | `path` | Yes | Local artifact file path to publish. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key` | `string` | - | Target key under the content kind prefix (defaults to filename). |
| `--replace` | `boolean` | - | Overwrite an existing immutable object when checksum differs. |
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops store sync`

**Upload queued artifacts from `store/pending.jsonl` to the content store.**

```bash
devops store sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops store ls`

**List objects stored under a content kind prefix.**

```bash
devops store ls [OPTIONS] <kind>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<kind>` | `string` | Yes | Content kind (`review-window`, `study`, or `review-session`). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prefix` | `string` | `` | Optional sub-prefix filter under the content kind root. |
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops store get`

**Download a stored object to a local file path.**

```bash
devops store get [OPTIONS] <kind> <key> <dest>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<kind>` | `string` | Yes | Content kind (`review-window`, `study`, or `review-session`). |
| `<key>` | `string` | Yes | Object key relative to the content kind prefix. |
| `<dest>` | `path` | No | Local destination file path (defaults to key basename). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Local destination file path (defaults to key basename). |
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops store url`

**Print the public web URL for a web-visible content-kind object.**

```bash
devops store url [OPTIONS] <kind> <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<kind>` | `string` | Yes | Content kind (`review-window`, `study`, or `review-session`). |
| `<key>` | `string` | Yes | Object key relative to the content kind prefix. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops store presign`

**Generate a temporary SigV4 presigned GET URL (at most 7 days).**

```bash
devops store presign [OPTIONS] <kind> <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<kind>` | `string` | Yes | Content kind (`review-window`, `study`, or `review-session`). |
| `<key>` | `string` | Yes | Object key relative to the content kind prefix. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--expires` | `integer` | `3600` | Presigned URL lifetime in seconds (maximum 604800 / 7 days). |
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops store doctor`

**Run put, list, get, presign, and delete canary checks on configured endpoints.**

```bash
devops store doctor [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--endpoint` | `string` | - | Additional S3 endpoint URL to test alongside `store.s3_endpoint`. |
| `--json` | `boolean` | - | Emit structured JSON output |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
