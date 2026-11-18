# Design

## Decisions
- **The gate reads each skill file through its link.** `generated_files` matches `.claude/skills/openspec-*/**/*`, and the glob of Python 3.14 starts `**` inside the link, so it reads `SKILL.md` through the link (tried on the 2.1 output). The scratch copy of the skill check writes regular files. 2.1 installs a skill only when its text differs (`shared-skill-install.js`), so it leaves a copy with the same text as it is, and the comparison finds no false difference. A link replaced by a copy with the same text passes: the tool itself also takes that copy as up to date.
- **Kilo Code reads `.agents/skills`.** The agent table of `skills` 1.8.1 gives Kilo Code `skillsDir: ".agents/skills"`, and 2.1 writes `kilocode` with no `own-files` in `.openspec-target` and deletes the copies in `.kilocode/skills`. The project keeps what the tool writes.
- **Each run takes its scratch directory as its home.** 2.1 refreshes the skills under the home (`~/.agents/skills` and the global folder of each agent) with the profile of the run, and writes `projects.json` in the data folder of the home. The four workflows of the isolated profile would remove the archive and sync skills of a person who installed the skills globally. With `HOME` set to the scratch configuration directory, a run finds no global skill and writes nothing under the home of the person. Git then reads no global configuration for its clone of a public repository.
- **`skillsScope: project` is written by hand.** The message of 2.1 says to add the key by hand when the tool cannot save it, and a non-interactive `update` never asks.
- **The generated skills keep no project edit.** 2.1 removes `generatedBy` and writes its own text, which the regeneration replaces whole. The project instructions stay in `openspec/config.yaml` and in the `devops-*` skills, which `update` does not write.
- **OpenSpec comes on the day of its release.** `"schedule": ["at any time"]` on the package rule; the rule keeps its group and its notes.

## Rejected alternatives
- **Record each link as a link in the scratch copy** (the design of the refine step): rejected. 2.1 takes a copy with the same text as up to date, so a link check would fail a tree that the tool itself accepts, and it adds code that the glob does not need.
- **Keep `.kilocode/skills/openspec-*` as links that the project makes after each update** (the design of the refine step): rejected. `skills` 1.8.1 names `.agents/skills` as the folder of Kilo Code, and 2.1 deletes the `.kilocode` copies on each update, so the skill check would report each link as a file that the tool does not write.
- **Leave `HOME` as the person's home**: rejected. A gate run on a machine with global OpenSpec skills rewrites them with the four workflows and writes `projects.json` under the home.
- **Set only `XDG_DATA_HOME`**: rejected. It moves `projects.json`, but the global skills are found under `os.homedir()`, which reads `HOME`.
- **`openspec init --scope project`**: rejected. `init` sets up the tools again, and ADR 0010 lets no agent run `init` directly; the key alone records the choice.
- **Skills from the npm package with no network**: rejected. 2.1 has no option for it: `installReleaseSkills` always gets the skills from the release tag of the repository.
- **Remove `opsx` from the generated descriptions by hand**: rejected. The skill check fails a hand edit of a generated skill.
