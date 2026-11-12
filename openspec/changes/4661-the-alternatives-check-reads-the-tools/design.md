# Design

## Decisions

- **The inventory has three sources, the cheapest first.** The SBOM costs one request for each run and holds the packages of every manifest, lock file and workflow. The deployed files of a clone cost no request. deps.dev costs one request for each checked tool that the first two do not hold, and only when the SBOM holds a package, because with no package in the SBOM no linked package can be in it. One run keeps the answer of deps.dev for each project.
- **The match of a package.** A package URL of the type `github` or `githubactions` matches by the first two segments of its namespace and name, so `pkg:githubactions/github/codeql-action/init` is the repository `github/codeql-action`. A PyPI package matches by its canonical name. The scoped npm package `@<owner>/<name>` of a GitHub project matches too, as `@devcontainers/cli` is `devcontainers/cli`.
- **The match of a deployed file.** The name of the repository, or of the PyPI package, as a whole word in any case: the rule of `git grep -i -w -F` that the census used. A symbolic link is not followed, and a path that the clone does not hold is left out.
- **The code rule runs after `rejected`.** An ADR that rejects a tool says more than an SBOM that holds it. Then the inventory, then the `in_use` flag of the model.
- **A failed read of deps.dev skips the item.** A verdict that the job cannot confirm either way would be a guess. The retry delay takes the item again later.
- **An ADR rejects a tool only when its rejected options alone name it.** An option that says `rejected` or `not chosen` names the tool, and the title and the other options do not. A title or a chosen option that names the tool means that the ADR adopts it, or decides on a part of it.
- **The canonical id is the deps.dev project key.** `github.com/<owner>/<name>` in lower case is the key that deps.dev uses, and a PyPI tool reaches it through the source URL of its PyPI record. A PyPI tool with no GitHub source keeps `pkg:pypi/<name>`. Another URL is its own id.
- **The ADR hash covers the entries that the model saw.** These are the entries in force after the token cut, so the hash changes when an ADR in force changes, when an ADR is superseded, and when the cut changes. The run reads the ADRs before it selects the items, because the hash selects them.
- **The Service row takes the clone of the model lane.** Stage and refine already make it, at the tip of the default branch, so the deployed files are the files at HEAD.
- **The inventory lives for one run.** The shared cache of the inventory by commit is the tiered cache item of the plan #4624.

## Rejected alternatives

- **The SBOM only.** The census measured that it holds 33 of the 58 tools in use. The other 25 are deployed services and CLIs.
- **`git grep` as a child process.** It is the census rule, but each test of a git child needs a recorded transcript for each command (docs/TESTING.md), and the census replay asks about 58 names. The regular expression `(?<!\w)<name>(?!\w)` with `re.IGNORECASE` is the same test, and the clone of the Service holds only the files of HEAD.
- **A parse of the manifests.** The plan of #4624 removed it: an image or a Helm chart names no package, and each manifest kind needs its own parser.
- **The name test of the old rule for `rejected`.** It confirmed #3258: ADR 0010 names OpenSpec in its chosen option.
- **A model call to read the sense of the ADR.** The issue asks for code rules with no model call, and the options of the ADRs of the repository say `rejected` or `not chosen` in plain words.
- **A recheck of every item after any change of `docs/adr/`.** A change of an ADR that is not in force, or that the cut leaves out, changes nothing that the model saw. The hash of the entries is narrower.
