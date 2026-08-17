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
| `--name`, `-n` | `string` | - | Filter by name |

---

## `devops docker build`

**Build a Docker image.**

```bash
devops docker build [OPTIONS] <context>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<context>` | `path` | No | Build context directory |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tag`, `-t` | `string` | - | - |
| `--file`, `-f` | `path` | - | - |
| `--no-cache` | `boolean` | - | - |

---

## `devops docker push`

**Push a Docker image to a registry.**

```bash
devops docker push <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Image name[:tag] to push |

---

## `devops docker prune`

**Remove unused containers, images, and networks.**

```bash
devops docker prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--volumes` | `boolean` | - | Also remove unused volumes |
| `--force`, `-f` | `boolean` | - | Skip confirmation |

---
