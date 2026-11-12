# Design

## Decisions

- **The stage layout.** Zensical needs `docs_dir` and `site_dir` under the folder of its config file. So `.data/site-src/` holds the staged config `zensical.yml`, the pages in `pages/` and the built site in `site/`. Each build deletes `pages/` and `site/` first, so a deleted document leaves the site. The `.cache/` of Zensical stays, and a second build takes about 5 s.
- **The staged config is YAML.** No TOML writer is a dependency (`tomli-w` and `tomlkit` are not in `uv.lock`). Zensical reads a config by its extension, and PyYAML is a dependency. `zensical.toml` holds no folder setting: the command owns the stage layout.
- **The repository paths stay.** The pages keep their repository paths, so each relative link that works on github.com works on the site, and the edit and view buttons go to the source file of the page (`edit_uri = "edit/main/"`).
- **The link change parses Markdown with tree-sitter-markdown.** The block grammar gives the inline nodes and the table cells, and the inline grammar finds the link and image destinations. A link in a code block or a code span is not a destination. Each inline node is parsed on its own: one parse over all inline nodes as included ranges took 4.8 s on the 890 kB `CHANGELOG.md` and missed 12 of its links. A link to a file goes to `blob/<sha>`, a link to a folder to `tree/<sha>` and an image to `raw/<sha>`. A link to a page of the site, a link with a scheme or a host, and a link to no repository file stay as they are, so the strict build reports a missing file.
- **The build data.** The version comes from `pyproject.toml`, the commit and its date from `git show --no-patch --format=%H%n%h%n%cs HEAD`, and the build time from the clock. A checkout with depth 1 has the commit, so the workflows need no tags.
- **The footer.** `overrides/partials/copyright.html` replaces the slot of the theme footer, and `overrides/main.html` adds the meta tag in the `extrahead` block of `base.html`. HTML allows a `meta` tag in `head` only.
- **The nav check reads the built site.** Each `index.html` under `site/` is a page. The command compares them with the `md-nav__link` targets of the home page. So the check sees the nav that Zensical made, and holds no copy of the glob rules of awesome-nav.
- **The checks of the workflows.** `docs-site.yml` runs on the site sources, `pyproject.toml`, `uv.lock` and the build code, so a Renovate update of Zensical builds the site before the merge. These paths hold release files, so the job skips the release pull request.

## Rejected alternatives

- **A Python-Markdown extension that changes the links at render time.** It needs the path of the page, which only the internal `zensical.extensions.context` holds. That couples the build to the internals of a beta.
- **A regular expression for the links.** It does not know code spans and code blocks, and CONTRIBUTING.md asks for a parser.
- **A copy of the theme `partials/footer.html`.** It is 56 lines of theme code that each theme update can change. The copyright slot is 15 lines.
- **A Python copy of the awesome-nav globs for the nav check.** It can match a page that Zensical does not, and the reverse.
- **The lychee step.** It excluded `/src/` and `.md` links, so it did not see the 183 links to repository files. The strict build checks each link and anchor of the Markdown.
- **`docs-site.yml` without the dependency files.** A Zensical update would reach `main` with no build, and `pages.yml` would fail after the merge.
