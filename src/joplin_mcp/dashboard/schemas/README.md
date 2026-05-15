# schemas/

Tracked dir. Holds JSON Schema files (in YAML form) that validate dashboard YAML configs.

- `dashboard_config.schema.yaml` — generic schema for the dashboard config format. Authored hand-in-sync with `docs/dashboard_config.md` (the human-readable contract). _Not yet created — pending the schema-validation TODO in `CLAUDE.md`._
- `<project>.schema.yaml` — optional per-project extension schemas. None exist yet; the dir is forward-compatible.

Consumer dashboard config files (e.g. `job_search.yaml`) do NOT live here — they live in `../configs/` as symlinks into the consumer repo.
