# MCP packaging / distribution infrastructure

Extract the archived Docker/install tooling into a reusable mcp-docker-dev repo.
- Source: the `archive/bulk-operations-monolith` tag (`3de13d4`); target: a new `MatthewOGoodman/mcp-docker-dev` repo, not yet created, as reusable infrastructure for any MCP project.
- Parked, not started. What the tag holds, and the reasoning, in `mcp-packaging-distribution-infrastructure_PLAN_design.md`.
- Dropped 2026-11-25 by user decision: upstream now ships its own Docker and install tooling, and no hand-off of this work exists elsewhere. The archive tag stays as reference.

## TODO

### Extract Docker and install infrastructure  [ ]

start: 2026-05-15 22:00; update: 2026-11-05 14:54
Move the archived snapshot's reusable pieces into their own repo.
- [ ] Extract from the `archive/bulk-operations-monolith` tag into the new repo; upstream now ships its own Dockerfile, `bootstrap.py` and PyPI/registry publishing, so scope this to what upstream lacks (hot-reload dev container, deployment switcher, `DOCKER_DEV.md` lessons)
