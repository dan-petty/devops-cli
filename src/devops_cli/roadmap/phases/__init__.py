"""The phases of a roadmap step that runs an agent: `prepare`, `agent` and `publish` (#3702, #6601).

The parent item #2695 splits a run into three trust zones. `prepare` holds the App key and runs no
agent code: it makes the GitHub reads, checks the claim and makes the clone. `agent` holds the
model key only: it runs the agent and its checks in the clone, makes no GitHub call, and writes its
outputs. `publish` holds the App key again: it reads the outputs of the agent as data, applies the
patch to a fresh clone, writes one commit, checks the claim again, pushes with a lease and makes the
GitHub writes of the outcome.

- `files.py`: the run folder (`state/`, `work/`, `out/`), the models of the agent outputs, and the
  read of an output as data.
- `patch.py`: the patch of the agent phase, made in a new git folder.
- `publish.py`: the patch applied as data and pushed as one commit. #6528 uses it for stage.

`devops roadmap step fix-checks` is the first step on the phases. #3700 runs each phase in its own
container; until then `--phase all` runs the three in one process.
"""
