"""`devops repos onboard`: one command onboards a GitHub repository (#6773, ADR 0035).

The command reads the live state of a repository, compares it with one baseline, and writes only
the differences. The baseline is the Copier template of `github.template_repository` at one ref:
its rendered files are the content of the template pull request, and its `github/repository.yaml`
holds the settings. Each row of `run.ROW_ORDER` is one step of the design of #6773, and each write
goes through one route of `routes.ROUTES`. `--plan` and `--confirm` run the same rows: the writer
records a write in a plan and sends it in a confirmed run. The steps that GitHub allows only a
person to do end the output.
"""
