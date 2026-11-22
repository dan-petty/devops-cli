# Tasks

## 1. Pins

- [x] 1.1 Pin the devtools image of the three references to `1.0.0` at its index digest
  - Verification: `$ git grep -c 'devtools:1.0.0@sha256:3dae8696' -- .devcontainer/Dockerfile Dockerfile .github/workflows/rule-pack.yml`
- [x] 1.2 Check that the tag holds the devtools release commit
  - Verification: `$ skopeo inspect --format '{{index .Labels "org.opencontainers.image.version"}}' docker://ghcr.io/dan-petty/devtools:1.0.0`
