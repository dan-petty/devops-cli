# Proposal: #5078

## Why
OpenSpec 2.1.0 was released on 2026-11-17. The tools lock pins 1.17.0. The owner asked on 2026-11-17 that the project takes each OpenSpec release when it is available and uses the newest standard for its planning documents. OpenSpec 2.x keeps one copy of each skill in `.agents/skills`, links the folders of a tool that reads only its own folder, removes the copies of the other tools, retires the `delivery` setting, and since 2.1 installs the skills with the `skills` package of Vercel. The gate, the recorded runs and the Renovate schedule still have the 1.x form. Closes #5078.

## What Changes
- The tools lock, `package.json` and `package-lock.json` of OpenSpec pin 2.1.0.
- The committed skills have the 2.1 layout: one copy of each of the four skills in `.agents/skills`, each `.claude/skills/openspec-*` a link to its folder there, no copy in `.kilocode/skills` (Kilo Code reads `.agents/skills`), and the three lines `agents`, `claude own-files`, `kilocode` in `.agents/skills/.openspec-target`.
- `openspec/config.yaml` records `skillsScope: project`, the choice that 2.1 reads to keep the skills in the repository. The configuration test allows that key.
- `.gitignore` re-includes `.claude/skills/openspec-*` with no end slash, because a pattern that ends in `/` matches no link.
- The isolated configuration no longer sets `delivery`. Each `openspec` run takes its scratch configuration directory also as its home, because 2.1 refreshes the skills that it finds under the home with the profile of the run.
- The globs of the generated files, the documentation inventory, the review routing and the `openspec-gate` hook no longer name `.kilocode/skills`.
- Renovate opens the OpenSpec pull request on the day of a release, not on the weekly schedule of the shared preset, and its note says that the regeneration needs Git and github.com.
- The runs of OpenSpec that the tests replay are recorded again with 2.1.0, and the fake says how 2.x writes the skills.
- No project document, skill or prompt names a `/opsx:` command (count 0, `git grep -n /opsx`). The descriptions that OpenSpec writes in its skills still name the phrase `opsx <workflow>`. They are generated text, so they stay as the tool writes them.
- Observable: the dry run of `devops openspec check` lists no `config set delivery` run and lists `HOME` for each run, and the skill check passes the 2.x layout. The change carries deltas of `openspec-check`. The scenarios of `openspec-check` and `tools-lock-install` that named the old pin name the locked version instead.

## Capabilities
- Modified: `openspec-check`, `tools-lock-install`.

## Impact
- `devops openspec check`, `devops openspec regenerate` and the `openspec-gate` hook need the 2.1.0 command on PATH: `uv run devops install-tools --tool openspec --only-missing`.
- When a committed skill differs from what the pinned tool writes, the regeneration (and the skill check of the gate, in its scratch copy) clones the release tag of `Fission-AI/OpenSpec` from github.com with Git. When the skills agree, no run makes a network request. The child environment keeps no token, so the request is anonymous.
- No run writes under the home of the person.
- Node 22.20.0 or newer is necessary; `.node-version` gives 24.
- `npm audit` still reports GHSA-fc5q-39xc-vjpf (picomatch, no released fix), which `.npm-audit-ignore.yaml` ignores until 2026-11-20 (#6204).
- It fits one pull request.

## Feasibility
- `openspec --version` printed `2.1.0` from an install of the new lockfile; `npm audit signatures` verified the registry signatures of all 66 packages.
- `openspec update --help` (2.1.0) has only `--force`, `--dry-run` and `--json`. `--scope project` is an option of `openspec init`. The release notes of v2.1.0 say: "In CI or from an agent there is no question: update refreshes the skills where they are", and that `openspec/config.yaml` records the choice. `dist/core/project-skills-scope.js` writes and reads `skillsScope: project`, and its message says to add the key by hand when the tool cannot.
- A trial on a scratch copy of the committed skills: `openspec update --dry-run` listed 17 changes (four updated skills, the target file, four `.claude` links, eight deleted files); `openspec update --force` wrote them in 2.1 s.
- `dist/core/shared/shared-skill-install.js` installs a skill only when its text differs from the text that the release expects, and `dist/core/skill-installer.js` installs through `installSkills('Fission-AI/OpenSpec/skills', { ref: 'v2.1.0' })` of `skills` 1.8.1, which runs `git clone --depth 1 --branch v2.1.0`.
- `dist/core/global-skills.js` reads `~/.agents/skills` and the global skill folder of each agent, and `update` refreshes them when it finds OpenSpec's skills there. `dist/core/known-projects.js` writes `projects.json` under the data folder of the home. 1.17.0 has neither.
- The agent table of `skills` 1.8.1 gives Kilo Code the project folder `.agents/skills`.
- `git check-ignore -v --no-index .claude/skills/openspec-explore` named `.gitignore:81` (`.claude/skills/*`) before the fix and the `!` rule after it.

## Existing Tool Considered
- OpenSpec 2.1.0 (MIT, https://github.com/Fission-AI/OpenSpec) writes the layout itself, and `skills` 1.8.1 of Vercel (MIT, https://github.com/vercel-labs/skills) installs the files. The project keeps only the gate around them.
- Internal code deleted: the `delivery` setting of the isolated configuration, and the `.kilocode/skills` globs of the gate, the documentation inventory and the review routing.
- Cost to build: one constant, one variable of the run environment and two tests, under 1 hour.
