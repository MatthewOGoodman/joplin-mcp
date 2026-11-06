# MCP packaging / distribution infrastructure

Extract the Docker/install infrastructure from the `archive/bulk-operations-monolith` tag (`3de13d4`) into a new `MatthewOGoodman/mcp-docker-dev` repo, not yet created, as reusable infrastructure for any MCP project. Parked, not started. What the tag holds, and the reasoning, in `markdowns/DESIGN_NOTES.md` → "Design: MCP packaging / distribution infrastructure".

## TODO

### Extract Docker and install infrastructure  [ ]

start: 2026-05-15 22:00; update: 2026-11-05 14:54
Move the archived snapshot's reusable pieces into their own repo.
- [ ] Extract from the `archive/bulk-operations-monolith` tag into the new repo; upstream now ships its own Dockerfile, `bootstrap.py` and PyPI/registry publishing, so scope this to what upstream lacks (hot-reload dev container, deployment switcher, `DOCKER_DEV.md` lessons)
