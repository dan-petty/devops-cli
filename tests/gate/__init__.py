"""The checks of committed files and tool configuration that rows of `devops ci` run, outside pytest (#2164).

Each module holds one row: its `main` prints what fails and returns the exit status. They live
outside `tests/support/` because `tests/support/bootstrap.py` imports a support module that
imports pytest or another support module at the start of every pytest process, and a pytest process
runs none of these.
"""
