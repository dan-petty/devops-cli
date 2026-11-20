## MODIFIED Requirements

### Requirement: The Dockerfile takes its tools from the devtools image
The `Dockerfile` SHALL name `ghcr.io/dan-petty/devtools` in one `FROM` line, with a tag and a digest, as the stage `devtools`, and Renovate SHALL move the tag and the digest in the `devtools` group. The `runner-deps` stage SHALL build FROM `devtools`. The Service and MCP server images SHALL copy from `devtools` only gh, kubectl and helm. The `Dockerfile` SHALL hold no tool version, download URL or checksum.

#### Scenario: The Dockerfile installs no tool
- **WHEN** a person runs `git grep -n -e 'releases/download' -e 'sha256sum' -- Dockerfile`
- **THEN** the command prints nothing
