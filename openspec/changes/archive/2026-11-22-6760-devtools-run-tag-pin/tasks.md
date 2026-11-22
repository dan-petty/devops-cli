# Tasks

## 1. Pins

- [x] 1.1 Pin the devtools image of the three references to `20261122.53` at its index digest
  - Verification: `$ git grep -c 'devtools:20261122.53' -- .devcontainer/Dockerfile Dockerfile .github/workflows/rule-pack.yml`
- [x] 1.2 Check that the tag holds the devtools commit with `make`
  - Verification: `$ skopeo inspect --format '{{index .Labels "org.opencontainers.image.revision"}}' docker://ghcr.io/dan-petty/devtools:20261122.53`
