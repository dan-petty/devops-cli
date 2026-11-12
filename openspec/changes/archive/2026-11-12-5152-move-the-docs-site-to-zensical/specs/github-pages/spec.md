## REMOVED Requirements

### Requirement: The site settings are in docs/_config.yml only
**Reason**: Zensical builds the site from `zensical.toml` at the repository root, and the Jekyll build is removed (#5152).
**Migration**: The requirement "devops gh pages verify checks zensical.toml" holds the rule for the new settings file.

### Requirement: devops gh pages verify checks docs/_config.yml
**Reason**: The site has no Jekyll settings file (#5152).
**Migration**: The requirement "devops gh pages verify checks zensical.toml" replaces it.

### Requirement: Default layout navigation links reach only built pages
**Reason**: `docs/_layouts/default.html` is removed, and the theme of Zensical draws the nav (#5152).
**Migration**: The requirement "Each built page is in a nav tab" checks the nav of the built site.

### Requirement: The documentation site removes source Markdown files
**Reason**: Its scenario reads the Jekyll setting `optional_front_matter` of `docs/_config.yml`, which is removed (#5152).
**Migration**: The requirement "The built site holds no source Markdown file" holds the rule for the Zensical build.

## MODIFIED Requirements

### Requirement: The documentation site provides an index home page

The site SHALL use `README.md` as its home page, as the first nav tab "Home". When built, the site root SHALL serve `index.html`. `docs/index.md` SHALL stay as the "Overview" page of the "Guides" tab.

#### Scenario: The documentation directory includes an index page

- **WHEN** `docs/index.md` is inspected
- **THEN** `docs/index.md` exists as a Markdown file with non-empty content
- **AND** `index.html` is generated at the site root during the build

#### Scenario: The home page is README.md

- **WHEN** `.nav.yml` of the repository is read
- **THEN** its first entry is the tab "Home" with `README.md`

## ADDED Requirements

### Requirement: The built site holds no source Markdown file

The built site output SHALL contain no raw `.md` files. The `Docs Site Build` check SHALL fail when the built site holds a `.md` file or has no `index.html` at its root.

#### Scenario: The check verifies the built site

- **WHEN** `.github/workflows/docs-site.yml` is read
- **THEN** its job builds the site with `uv run devops docs site build --strict`
- **AND** a later step named "Verify Built Site Pages" checks the built site

### Requirement: devops gh pages verify checks zensical.toml

`devops gh pages verify` SHALL read `zensical.toml` at the project root, and SHALL pass only when that file is valid TOML with a value for each of `site_name`, `site_url` and `repo_url` in its `[project]` table, and `docs/` holds a Markdown file.

#### Scenario: A complete zensical.toml passes

- **WHEN** `zensical.toml` sets `site_name`, `site_url` and `repo_url`, and `docs/` holds a Markdown file
- **THEN** the check passes and reports that the Zensical configuration is valid

#### Scenario: A missing zensical.toml fails

- **WHEN** the project root has no `zensical.toml`, and a `mkdocs.yml` sets the site settings
- **THEN** the check fails and the diagnostic names `zensical.toml`

#### Scenario: A zensical.toml with missing settings fails

- **WHEN** `zensical.toml` sets `site_name` only
- **THEN** the check fails and the diagnostic names `site_url` and `repo_url`

#### Scenario: A zensical.toml that is not TOML fails

- **WHEN** `zensical.toml` holds a table header with no closing bracket
- **THEN** the check fails and the diagnostic names the invalid TOML syntax

### Requirement: devops docs site build stages the site pages at their repository paths

`devops docs site build` SHALL copy `docs/` without `docs/agent/`, the root documents `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `RELEASE_CYCLE.md`, `CONTEXT.md`, `AGENTS.md` and `CHANGELOG.md`, and `.nav.yml` to `.data/site-src/pages/` at their repository paths. It SHALL delete the pages and the built site of an earlier build first.

#### Scenario: The stage holds the site pages

- **WHEN** the site of a repository with `docs/agent/README.md` is staged
- **THEN** the stage holds the root documents, `.nav.yml` and the files of `docs/`
- **AND** the stage holds no file of `docs/agent/`

#### Scenario: A missing root document fails the stage

- **WHEN** the repository has no `CONTEXT.md`
- **THEN** the stage fails with the error code `DOCS_SITE_INVALID`, and the details name `CONTEXT.md`

#### Scenario: A deleted page leaves the site

- **WHEN** a page of `docs/` is deleted after a build, and the site is staged again
- **THEN** the stage does not hold the page

### Requirement: The staged config adds the stage folders and the build data

The stage SHALL write `.data/site-src/zensical.yml` with each setting of `zensical.toml`, `docs_dir` `pages`, `site_dir` `site`, `theme.custom_dir` set to the `overrides/` folder of the repository, and `extra.build` with the build data.

#### Scenario: The staged config keeps the site settings

- **WHEN** the site of a repository with `zensical.toml` is staged
- **THEN** the staged config holds each setting of `zensical.toml`, the two stage folders, the overrides folder and the build data

### Requirement: The stage changes a link to a repository file outside the site into a GitHub link

The stage SHALL change each relative link of a staged page to a repository file or folder that the site does not publish into a link at the build commit: `blob` for a file, `tree` for a folder and `raw` for an image, with the query and the fragment. It SHALL keep a link to a page of the site, a link with a scheme or a host, a link to no repository file, and the text of code.

#### Scenario: Links to files outside the site go to GitHub

- **WHEN** `README.md` links to `src/x.py#L1`, `k8s/` and `docs/agent/README.md`, and a page of `docs/guide/` links to `../../src/x.py`
- **THEN** each link goes to GitHub at the build commit, with `blob` for a file and `tree` for the folder
- **AND** a link to `docs/TESTING.md#run-time` stays relative
- **AND** a link in a code span or a code block keeps its text

### Requirement: Each built page shows the build data

The build data SHALL hold the version of `pyproject.toml`, the commit of the checkout, its short form and date from git, the link of the commit and the build time in UTC. Each built page SHALL show them in its footer and hold the commit in the meta tag `devops-build-commit`. A built page whose meta tag does not hold the build commit SHALL be a defect of the built site.

#### Scenario: The build data comes from the checkout

- **WHEN** git gives the commit, its short form and its date
- **THEN** the build data holds the version of `pyproject.toml`, the three values and the link of the commit

#### Scenario: A checkout with no commit has no build data

- **WHEN** `git show` exits with code 128
- **THEN** the command fails with the error code `SUBPROCESS_FAILED` and the exit code 128

#### Scenario: A page without the build commit is a defect

- **WHEN** a built page holds another commit in its meta tag
- **THEN** the check of the built site names the page as a page without the build commit

### Requirement: Each built page is in a nav tab

Each built page SHALL have a link in the nav of the home page. A built page with no nav link SHALL be a defect of the built site. With `--strict`, a defect SHALL fail the command and name the page. Without `--strict`, the command SHALL warn and name the page.

#### Scenario: A page that no tab lists fails a strict build

- **WHEN** Zensical builds a page that the nav of the home page does not list, and the command runs with `--strict`
- **THEN** the command exits 1 and names the page

#### Scenario: A page that no tab lists warns without strict

- **WHEN** Zensical builds a page that the nav of the home page does not list, and the command runs without `--strict`
- **THEN** the command exits 0 and names the page

### Requirement: A strict site build fails on a Zensical warning

`devops docs site build --strict` SHALL run `zensical build --config-file .data/site-src/zensical.yml --strict`, so a link to a missing page or anchor fails the build. A Zensical build that fails SHALL fail the command with its exit code.

#### Scenario: The strict build runs Zensical with --strict

- **WHEN** the command runs with `--strict`, and Zensical builds each page with a nav link and the build commit
- **THEN** Zensical runs with `--strict` on the staged config
- **AND** the command exits 0 and reports the pages, the version and the commit

#### Scenario: A failed Zensical build fails the command

- **WHEN** Zensical exits with code 1
- **THEN** the command exits 1

### Requirement: devops docs site build --serve serves the staged site

With `--serve`, the command SHALL stage the site and run `zensical serve --config-file .data/site-src/zensical.yml`. It SHALL check no built page.

#### Scenario: The command serves the staged site

- **WHEN** the command runs with `--serve`
- **THEN** Zensical runs `serve` on the staged config, and the command exits 0

### Requirement: The MCP tool catalog links each tool to the heading id that GitHub writes

The table of `docs/MCP_TOOLS.md` SHALL link each tool to the id that GitHub writes for its heading, with the underscores of the tool name kept.

#### Scenario: The link of ai_ask_jev keeps its underscores

- **WHEN** the catalog of the tool `ai_ask_jev` is written
- **THEN** its table row links to `#ai_ask_jev`
