# github-pages Specification

## Purpose
Keeps the settings of the GitHub Pages documentation site in the one file that the Pages build reads, and checks that file locally with `devops gh pages verify`.

## Requirements

### Requirement: The site settings are in docs/_config.yml only

The repository SHALL keep every setting of the documentation site in `docs/_config.yml`, and SHALL have no other YAML file at the top of `docs/`. GitHub Pages builds `main:/docs` and runs Jekyll with no `--config` option, so Jekyll reads `docs/_config.yml` and no other file.

#### Scenario: The repository has one site configuration file

- **WHEN** the top level of `docs/` of the repository is listed
- **THEN** `_config.yml` is the only YAML file
- **AND** `devops gh pages verify` passes on the repository

### Requirement: devops gh pages verify checks docs/_config.yml

`devops gh pages verify` SHALL read `docs/_config.yml` under the project root, and SHALL pass only when that file is valid YAML with a value for each of `title`, `url`, `baseurl` and `markdown`, and `docs/` holds a Markdown file.

#### Scenario: A complete docs/_config.yml passes

- **WHEN** `docs/_config.yml` sets `title`, `url`, `baseurl` and `markdown`, and `docs/` holds a Markdown file
- **THEN** the check passes and reports that the Jekyll configuration is valid

#### Scenario: A missing docs/_config.yml fails

- **WHEN** `docs/` has no `_config.yml`
- **THEN** the check fails and the diagnostic names `_config.yml`

#### Scenario: Settings in a different file fail

- **WHEN** `docs/` has no `_config.yml`, and a different YAML file in `docs/` sets `title`, `url`, `baseurl` and `markdown`
- **THEN** the check fails and the diagnostic names `_config.yml`

#### Scenario: A docs/_config.yml with missing keys fails

- **WHEN** `docs/_config.yml` sets `title` only
- **THEN** the check fails and the diagnostic names the missing Jekyll configuration keys

### Requirement: The documentation site provides an index home page

The repository SHALL maintain `docs/index.md` as the home page that routes visitors to the primary documentation guides. When built, the site root SHALL serve `index.html`.

#### Scenario: The documentation directory includes an index page

- **WHEN** `docs/index.md` is inspected
- **THEN** `docs/index.md` exists as a Markdown file with non-empty content
- **AND** `index.html` is generated at the site root during the build

### Requirement: The documentation site removes source Markdown files

The documentation site settings in `docs/_config.yml` SHALL configure `optional_front_matter.remove_originals: true`. The built site output SHALL contain no raw `.md` files.

#### Scenario: Built site contains no source Markdown files

- **WHEN** `docs/_config.yml` is inspected
- **THEN** `optional_front_matter` sets `remove_originals` to `true`
- **AND** no `.md` files exist in the built site output

### Requirement: Default layout navigation links reach only built pages

The default site layout in `docs/_layouts/default.html` SHALL contain no links to `/ARCHITECTURE.html` or non-existent built pages. Every navigation and footer link SHALL resolve to a built page or external repository target.

#### Scenario: Layout contains no broken Architecture link

- **WHEN** `docs/_layouts/default.html` is inspected
- **THEN** neither header navigation nor footer contains `/ARCHITECTURE.html`
