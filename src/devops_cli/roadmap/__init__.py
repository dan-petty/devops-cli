"""The roadmap: Items, milestones and board fields, read and written through one store.

A milestone is a planning bucket, not a release. Callers open a store with
`devops_cli.roadmap.store.get_roadmap_store`, looked up through its module, so that a test can
replace that one factory with the in-memory adapter.
"""
