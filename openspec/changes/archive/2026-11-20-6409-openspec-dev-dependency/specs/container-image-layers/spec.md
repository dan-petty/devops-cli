## MODIFIED Requirements

### Requirement: The Dockerfile takes its tools from the devtools image
The `Dockerfile` SHALL name `ghcr.io/dan-petty/devtools` in one `FROM` line, with a tag and a digest, as the stage `devtools`, and Renovate SHALL move the tag and the digest in the `devtools` group. The `runner-deps` stage SHALL build FROM `devtools`. The Service and MCP server images SHALL copy from `devtools` only gh, kubectl and helm. The `Dockerfile` SHALL hold no tool version, download URL or checksum, and SHALL not run `devops install-tools`.

#### Scenario: The Dockerfile installs no tool
- **WHEN** a person runs `git grep -n -e 'install-tools' -e 'releases/download' -e 'sha256sum' -- Dockerfile`
- **THEN** the command prints nothing

## REMOVED Requirements

### Requirement: The Service image runs OpenSpec of the devtools image
**Reason**: The `openspec` stage installs OpenSpec from the root `package-lock.json` of the project, so the OpenSpec of the devtools image has no effect on the Service and MCP server images (#6409).
**Migration**: The requirement "The Service image runs OpenSpec of the root lockfile" holds the stage and its proof.

## ADDED Requirements

### Requirement: The Service image runs OpenSpec of the root lockfile
The `openspec` stage SHALL build FROM the `node` stage, copy `package.json` and `package-lock.json`, run `npm ci --omit=optional --ignore-scripts`, keep only OpenSpec in the `package.json` of the tree and run `npm prune --offline --ignore-scripts`, so the tree holds OpenSpec at the version of `package-lock.json` and the packages that it needs, and no Style Dictionary. The official Node binary of the `node` stage SHALL run it, because the Service image is on trixie.

#### Scenario: OpenSpec runs in the Service image
- **WHEN** a person runs `docker run --rm --entrypoint openspec <service image> --version`
- **THEN** the command prints the `@fission-ai/openspec` version of `package-lock.json` and exits 0

#### Scenario: The stage holds no Style Dictionary
- **WHEN** a person builds `--target openspec` and lists `node_modules` of `/usr/local/lib/openspec` in the result
- **THEN** the list holds `@fission-ai` and no `style-dictionary`
