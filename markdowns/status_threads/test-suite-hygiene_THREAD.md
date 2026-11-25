# Test suite hygiene

Resolve long-standing test failures so the suite can catch real regressions.
- The failures predate current work and were verified on a clean tree (via `git stash`) in two separate sessions without being tracked anywhere.
- Surfaced by the 2026-07-28 cleanup from the 2026-06-06 and 2026-06-09 session records, where both sessions independently confirmed and then set them aside.

## TODO

### Resolve four pre-existing test failures  [x]

start: 2026-07-28 15:58; update: 2026-11-25 10:28
The full suite reports 1054 passed with these 4 failing; they are unrelated to recent feature work but mask genuine regressions.
- [x] 4 failures in `tests/test_import_utils.py` — timezone-dependent epoch tests; fixed in `b9b3108`, CI runs UTC and America/Los_Angeles
- [x] 1 failure in `tests/test_config.py` — home-token leak (fixed upstream; gone after the v0.10.0 sync)
- [x] Decide per failure: fix, or mark `xfail` with a reason so a real regression is not hidden by an expected-red suite
