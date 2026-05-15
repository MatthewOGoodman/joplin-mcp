# Dashboard Config Schema + Validation — Corrected Plan

## Context

The dashboard subpackage (`src/joplin_mcp/dashboard/`) currently loads YAML configs into dataclasses with hand-written `ValueError` checks for missing required keys. Consumer projects (first: job_search) author dashboard YAML configs against an informally-documented schema; there is no machine-readable contract, no validation feedback, and no typo-catching. This plan adds a JSON Schema validator at the config-load boundary so consumers get fail-fast, multi-error feedback with JSON Pointer paths, and the config format is documented in one canonical place.

This work was previously queued as an inline TODO in `joplin-mcp/CLAUDE.md`. That location was wrong (plans belong in `markdowns/plans_draft/`, not CLAUDE.md) and the TODO content contained errors (stale `.gitkeep` references after the scaffold landed) and gaps (no `additionalProperties: false`, no `$schema` declaration, fragile drift-test design, cross-repo fixture dependency). **This plan replaces that TODO entirely; the TODO section is removed from CLAUDE.md as part of Phase 5.**

## Current state of the feature

**Already done** (mini-plan executed earlier this session, 2026-05-15):
- `src/joplin_mcp/dashboard/schemas/` dir with `README.md` (tracked, empty of schemas)
- `src/joplin_mcp/dashboard/configs/` dir with `README.md` (gitignored otherwise)
- `.gitignore`: `configs/*` ignored except `README.md`
- CLAUDE.md "Dashboard Subpackage" note corrected (schemas-vs-configs nomenclature)

**Not yet done** (this plan covers everything below):
- No JSON Schema file exists yet
- No `docs/dashboard_config.md` exists yet
- No `jsonschema` dependency
- No validator wiring in `dashboard/config.py`
- No `--validate` CLI mode
- No symlink-discovery (`joplin-dashboard <name>`)
- No fixtures, no schema tests, no drift test
- No symlink in `configs/` pointing at job_search's YAML (it stays gitignored regardless; can be added per-machine after the feature ships)

## Design decisions

### Carried forward from the cross-session relay (2026-05-13)

- Two-dir layout: `schemas/` tracked, `configs/` gitignored
- Validation library: `jsonschema` (canonical Python lib; not pydantic-via-schema — heavier, changes runtime model)
- Schema authoring: hand-kept-in-sync with `docs/dashboard_config.md`
- Per-project schemas (`<project>.schema.yaml`): deferred until a consumer demands one

### Added by 2026-05-15 critical review

1. **`additionalProperties: false`** at top-level object AND each section. Typo-catching is the primary practical benefit of validation; without this, typos like `group_by_tag_prefx` silently no-op.
2. **`$schema: "https://json-schema.org/draft/2020-12/schema"`** declared in the schema file. Without it, validator behavior is implementation-defined.
3. **Dep pin: `jsonschema>=4.18,<5`** (Draft202012Validator default). Aligns with project pinning style (`>=X,<Y`, e.g., `pydantic>=2,<3`). Looser pins risk drift.
4. **`columns` is `array<string>` free-form**, NOT enum. Reason: dashboard supports built-in column names (`title`, `tags`, `notebook`, `updated`, `created`, `id` — see `render.py:115-126`) AND arbitrary frontmatter field names as columns (fallback at `render.py:128-131`). Built-ins are documented but not enforced.
5. **YAML form for the schema file** (`dashboard_config.schema.yaml`). Loaded via `yaml.safe_load()` then handed to `jsonschema`. Allows inline comments; canonical JSON form is unnecessary at this scale.
6. **Multi-error reporting via `iter_errors()`**. Single `validate()` raises on first error; `Draft202012Validator(schema).iter_errors(instance)` collects all errors in one pass — better UX, especially for consumers authoring new configs.
7. **`format_validation_errors()` helper**. Convert each `ValidationError` to `<json-pointer-path>: <message>`. CLI prints all collected errors, exits 2. Avoids dumping Python tracebacks at users.
8. **Drift-guardrail test = canonical-example-validates**, NOT heading-match. Embed a labeled `<!-- canonical-example -->` YAML code block in `docs/dashboard_config.md`. Test extracts that block and validates it against the schema. Catches **semantic drift**, not just key-set drift (the original heading-match design only caught typos in property names, while still allowing the spec text and schema constraints to drift apart).
9. **Remove redundant dataclass `ValueError` raises** at `config.py:47-48, 50-51, 52-53, 66-67`. After schema validation at `load_config()` entry, those branches become unreachable for any input that reaches the dataclass step. Keeping them = two slightly different validators that will drift.
10. **Test fixtures inside joplin-mcp**, not cross-repo file deps. `tests/fixtures/dashboard_config_minimal.yaml`, `tests/fixtures/dashboard_config_full.yaml`. Validation against job_search's real `.yaml` is a manual one-shot check at acceptance time, not a unit test (otherwise CI breaks any time job_search is absent or moves files).
11. **`joplin-dashboard --validate` mode**: parse + validate config, print "valid" or formatted errors, exit 0/2. No render, no Joplin REST calls. Trivial addition once validation is wired.
12. **`joplin-dashboard <name>` symlink-discovery**: if positional arg is a bare name (no path separator, no `.yaml` extension, not an existing path), look up `<package-dir>/configs/<name>.yaml`. Use `Path.resolve(strict=True)` to detect broken symlinks; raise clean error on missing-file or broken-symlink. Resolve order: existing-path → bare-name-via-configs-dir → error.
13. **Schema meta-validation**: call `Draft202012Validator.check_schema(schema)` once at module import. Catches typos in our schema (e.g., `"type": "intgr"`) before any consumer config hits the validator.

## Files to create / modify

### New files

| Path | Purpose |
|---|---|
| `src/joplin_mcp/dashboard/schemas/dashboard_config.schema.yaml` | JSON Schema (YAML form). `$schema` declared. `additionalProperties: false` top-level + per-section. All keys explicit. |
| `docs/dashboard_config.md` | Human-readable key-by-key spec. Includes the labeled `<!-- canonical-example -->` block consumed by the drift test. |
| `tests/fixtures/dashboard_config_minimal.yaml` | Smallest valid config (`output` + one `section` with `title` only). |
| `tests/fixtures/dashboard_config_full.yaml` | Realistic config exercising every key including `group_by_tag_prefix`, frontmatter-passthrough columns, sort overrides. |
| `tests/test_dashboard_schema.py` | Schema validation tests (positive, negative, meta-validation, canonical-example-validates, multi-error). |

### Modify

| Path | Change | Notes |
|---|---|---|
| `pyproject.toml` | Add `jsonschema>=4.18,<5` | Line ~33-45 (deps block); match existing `>=X,<Y` style |
| `src/joplin_mcp/dashboard/config.py` | Add module-level cached validator; validate in `load_config()` before dict→dataclass; remove redundant ValueError raises | Specific lines: drop 47-48, 50-51, 52-53, 66-67 |
| `src/joplin_mcp/dashboard/cli.py` | Add `--validate` flag; symlink-discovery in arg handling; catch `ConfigValidationError`, format via helper, exit 2 | `main()` is at lines 19-40; existing `--dry-run` flag at 25-29 is the pattern |
| `CLAUDE.md` | **Remove** the inline "TODO: Dashboard config schema + validation" section entirely. Replace with a one-line entry under `## TODO: Future Development`: "Dashboard config schema + validation — see `markdowns/plans_draft/CLAUDE.PLANS_…_DASHBOARD_CONFIG_SCHEMA_VALIDATION.md`" | Plan-as-content does not belong in CLAUDE.md |
| `~/.claude/STATUS.md` Blockers | Once shipped: flip `joplin-dashboard CLI + schemas dir` to `[ready]` or remove | Done at commit time, not before |

### Existing code to reuse / preserve

- `src/joplin_mcp/dashboard/cli.py:19-40` — `main()` entry pattern; FileNotFoundError/ValueError catches already in place
- `src/joplin_mcp/dashboard/config.py:16-38` — dataclass definitions stay as runtime types (schema gates input; dataclasses construct)
- `src/joplin_mcp/dashboard/config.py:65-78` — `_section_from_dict()` keeps the dict→dataclass mapping; loses only the missing-title raise
- `tests/test_dashboard_config.py:10-13` — `_write(tmp_path, content) -> Path` helper to follow for fixture loading
- `tests/test_dashboard_cli.py:35-46` — `_write_config()` helper pattern
- `tests/test_dashboard_cli.py:14-21` — `FakeLoader` pattern keeps Joplin REST out of tests

## Implementation phases

### Phase 1 — Schema file + docs + dep

1. Hand-author `docs/dashboard_config.md`: introduction, per-key reference, examples, the `<!-- canonical-example -->` code block.
2. Hand-author `src/joplin_mcp/dashboard/schemas/dashboard_config.schema.yaml` to match. `$schema` declaration. `additionalProperties: false` at top-level and inside the `sections` items. All keys with explicit `type`, `default` where applicable, `description` (short).
3. Add `jsonschema>=4.18,<5` to `pyproject.toml`.
4. `pip install -e .` to pull the new dep.

### Phase 2 — Validator wiring (`config.py`)

5. Define new `ConfigValidationError` exception (subclass `ValueError` for backward compatibility with the existing CLI catch).
6. Add module-level cached validator:
   - Load schema YAML once at import.
   - `Draft202012Validator.check_schema(schema)` (meta-validation).
   - Construct `_validator = Draft202012Validator(schema)`.
7. In `load_config()`, immediately after `yaml.safe_load()`, run `errors = list(_validator.iter_errors(raw))`. If non-empty, raise `ConfigValidationError(errors)` carrying the list.
8. Delete the manual `ValueError` raises at lines 47-48, 50-51, 52-53, 66-67. Verify by running existing `tests/test_dashboard_config.py` — happy-path tests should still pass; old error-path tests will fail and need updating in Phase 4.

### Phase 3 — CLI enhancements (`cli.py`)

9. Add `format_validation_errors(errors: list[ValidationError]) -> str` helper. Each line: `<json-pointer-from-absolute_path>: <message>`.
10. Add `--validate` flag via `argparse`. When set: load + validate only, print "valid" on success or formatted errors on failure, exit 0/2. Bypass the render step.
11. Add symlink-discovery in `main()`:
    - If positional arg has no path separator (`/`), no `.yaml` extension, and `Path(arg)` does not exist → treat as bare name.
    - Look up `Path(__file__).parent / 'configs' / f'{arg}.yaml'`.
    - `resolve(strict=True)` to surface broken symlinks as clean errors.
12. Catch `ConfigValidationError` around the `load_config()` call in `main()`. Print via helper, exit 2.

### Phase 4 — Tests

13. `tests/fixtures/dashboard_config_minimal.yaml` — smallest valid config.
14. `tests/fixtures/dashboard_config_full.yaml` — exhaustive.
15. `tests/test_dashboard_schema.py`:
    - `test_schema_is_valid_meta()` — calls `check_schema` against the schema itself.
    - `test_minimal_fixture_validates()`, `test_full_fixture_validates()`.
    - Negative tests: missing-output, missing-title, unknown-top-level-key (verifies `additionalProperties: false`), unknown-section-key, wrong-type-per-key.
    - `test_canonical_example_validates()` — extract the `<!-- canonical-example -->` YAML block from `docs/dashboard_config.md`, validate against the schema.
    - `test_iter_errors_returns_multiple()` — config with two distinct errors; assert both surfaced (proves single-pass multi-error reporting).
16. Update `tests/test_dashboard_config.py`:
    - Remove now-obsolete tests for the deleted manual `ValueError` raises.
    - Add tests that schema-driven failures raise `ConfigValidationError` (which is a `ValueError` subclass, so CLI catch still works).
17. Extend `tests/test_dashboard_cli.py`:
    - `test_cli_validate_mode_pass()`, `test_cli_validate_mode_fail()` — exit codes 0/2.
    - `test_cli_resolves_bare_name_via_configs_dir()` — drop a symlink in a tmp configs dir; assert it resolves.
    - `test_cli_broken_symlink_error()` — broken symlink in configs/; assert clean error, not traceback.

### Phase 5 — CLAUDE.md cleanup + plan archival + commit

18. **Remove** the long "TODO: Dashboard config schema + validation" section from `CLAUDE.md` entirely.
19. **Add** one short stub under `## TODO: Future Development`:
    ```markdown
    ### Dashboard config schema + validation
    See `markdowns/plans_draft/CLAUDE.PLANS_20260515_<words>_DASHBOARD_CONFIG_SCHEMA_VALIDATION.md`. Status: in-progress.
    ```
20. **Move** this plan from `~/.claude/plans/` (transient plan-mode location) into the project at `markdowns/plans_draft/CLAUDE.PLANS_20260515_<random-words>_DASHBOARD_CONFIG_SCHEMA_VALIDATION.md` (per project plan-filename convention).
21. **Commit** with `feat:` prefix. Files: `pyproject.toml`, `src/joplin_mcp/dashboard/config.py`, `src/joplin_mcp/dashboard/cli.py`, `src/joplin_mcp/dashboard/schemas/dashboard_config.schema.yaml`, `docs/dashboard_config.md`, `tests/fixtures/*.yaml`, `tests/test_dashboard_schema.py`, `tests/test_dashboard_config.py`, `tests/test_dashboard_cli.py`, `CLAUDE.md`, `markdowns/plans_draft/CLAUDE.PLANS_…`.
22. **On verified ship**: `plan_backup.sh --completed` archives the plan to `plans_completed/`. Flip the user-global `~/.claude/STATUS.md` Blockers entry `joplin-dashboard CLI + schemas dir` to `[ready]` or remove.

## Verification (end-to-end)

1. `pytest tests/test_dashboard_*.py` — all green.
2. `joplin-dashboard --validate tests/fixtures/dashboard_config_minimal.yaml` → prints "valid", exits 0.
3. Hand-author a broken YAML (e.g., copy `dashboard_config_full.yaml` to `/tmp/broken.yaml`, change `sort_dir` to an unknown value, add an extraneous key). Run `joplin-dashboard --validate /tmp/broken.yaml`. Expect formatted multi-line error with JSON Pointer paths (`/sections/0/sort_dir: ...`, `/extra_key: Additional properties are not allowed`), exit 2.
4. **Manual real-consumer validation**: `joplin-dashboard --validate ~/projects/dev/job_search/dashboards/job_search.yaml` → must print "valid". If errors surface, either (a) tighten the consumer YAML, or (b) widen the schema. Document the resolution.
5. **Symlink-discovery smoke test**: `ln -s ~/projects/dev/job_search/dashboards/job_search.yaml src/joplin_mcp/dashboard/configs/job_search.yaml`; `joplin-dashboard --validate job_search` (bare name) → "valid". `joplin-dashboard job_search` (no flag) renders the dashboard. Remove the symlink after (it's gitignored, but cleanup is courteous).
6. **Drift-test smoke**: temporarily edit `docs/dashboard_config.md` canonical example to use a typo (`group_by_tag_prefx`); run `pytest tests/test_dashboard_schema.py::test_canonical_example_validates` — must fail. Revert.
7. **Backward compat**: existing tests in `tests/test_dashboard_*.py` (pre-this-change) keep passing.

## Out of scope (deferred separately)

- **Notebook-path support in `JoplinRestLoader`** — `loader.py:64-74` `_build_query()` would need path-based notebook syntax. Other open job_search blocker; gets its own TODO/plan once this lands.
- **`joplin-dashboard` global discoverability wrapper + `manifest.txt`** — existing separate TODO in CLAUDE.md.
- **Per-project schemas** (`<project>.schema.yaml`) — no consumer demand yet.
- **Schema-as-source-of-truth, docs generated from schema** — hand-sync for v1; revisit if schemas multiply.
- **Schema versioning field** — premature; no `version:` key in v1.
- **Backward-compat shim for the old `ValueError` raises** — the new `ConfigValidationError` subclasses `ValueError`, so existing CLI catches still work. No shim needed.
