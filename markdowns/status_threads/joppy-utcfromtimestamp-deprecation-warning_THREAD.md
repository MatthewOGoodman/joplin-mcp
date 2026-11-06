# Joppy `utcfromtimestamp` deprecation warning

`joppy/data_types.py:116` emits `DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version.` on every `joplin-dashboard` invocation. Cosmetic CLI noise; surfaced from a job_search session 2026-05-15. Deferred 2026-05-18 in favor of waiting on an upstream joppy fix — deprecated in CPython 3.12 with no removal version announced yet.

## TODO

### Decide how to silence the deprecation  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Revisit if joppy has not fixed it by the time a CPython removal version is announced.
- [ ] Choose one: bump `joppy` (if fixed upstream), suppress the warning at joplin-mcp's entry point, or submit an upstream PR
