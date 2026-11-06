# mdsync follow-ups

Residual verification left over from the shipped mdsync subpackage (`bbacf38`). The feature itself is done, committed, and dogfooded; the completed record is archived in `markdowns/session_archive/SWEPT_20260728_1558.md`.

## TODO

### Verify Joplin renders API-pushed GFM tables  [ ]

start: 2026-06-05 20:10; update: 2026-07-28 15:58
Confirm a GFM table survives the API round-trip visually; add a reformatter only if it does not.
- [ ] Visually check test note "mdsync test" (Testing notebook, id `ac0f9049…`), which already contains a GFM table
- [ ] Add a reformatter ONLY if the render is broken — do not pre-emptively build one
