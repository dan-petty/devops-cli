# `devops docker`

Docker image management.

## Commands

## `devops docker images`

**List local Docker images.**

```bash
devops docker images [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Filter containers or images by name. |

---

## `devops docker build`

**Build a Docker image.**

```bash
devops docker build [OPTIONS] <context>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<context>` | `path` | No | Build context directory. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tag`, `-t` | `string` | - | Image tag name. |
| `--file`, `-f` | `path` | - | Path to Dockerfile. |
| `--no-cache` | `boolean` | - | Do not use cached image layers when building. |

---

## `devops docker push`

**Push a Docker image to a registry.**

```bash
devops docker push <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Docker image name or repository tag. |

---

## `devops docker prune`

**Remove unused containers, images, and networks.**

```bash
devops docker prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--volumes` | `boolean` | - | Include or prune volumes. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |

---

## `devops docker stats`

**Display live container CPU, memory, and network I/O statistics.**

```bash
devops docker stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Filter containers or images by name. |
| `--watch`, `-w` | `boolean` | - | Continuously refresh output in the terminal at a fixed interval. |
| `--interval`, `-i` | `float` | `2.0` | Auto-refresh polling interval in seconds. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops docker analyze-layers`

**Analyze container image layer efficiency and wasted space using Dive.**

```bash
devops docker analyze-layers [OPTIONS] <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Docker image name or repository tag. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops docker sandbox`

**Execute workload inside an isolated, disposable Docker container sandbox.**

```bash
devops docker sandbox [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | Yes | Workload command to execute inside container sandbox |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--image`, `-i` | `string` | `python:3.14-slim` | Docker container image to execute within |
| `--workspace`, `-w` | `path` | `.` | Workspace directory to mount |
| `--memory`, `-m` | `string` | `2g` | Memory limit (e.g. 2g, 512m) |
| `--cpus`, `-c` | `float` | `2.0` | CPU limit |
| `--network`, `-n` | `string` | `bridge` | Network mode: bridge | none | host |
| `--read-only` | `boolean` | - | Mount workspace as read-only |
| `--rootless`, `--root` | `boolean` | `True` | Run container with host user UID/GID |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
