"""The roadmap: Items, milestones and board fields, read and written through one store.

A milestone is a planning bucket, not a release. Callers open a store with
`devops_cli.roadmap.store.get_roadmap_store`. A test installs the in-memory adapter as the store
of every caller with `install_roadmap_store`.
"""
