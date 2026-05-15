# configs/

Gitignored dir (contents). Holds symlinks to consumer dashboard YAML config files.

Each entry is a symlink pointing into the owning consumer repo, e.g.:

```
configs/job_search.yaml -> ~/projects/dev/job_search/dashboards/job_search.yaml
```

The future `joplin-dashboard <name>` CLI does symlink-discovery here: `joplin-dashboard job_search` resolves `configs/job_search.yaml` and renders against it. (CLI symlink-discovery convention is pending — see the schema TODO in `CLAUDE.md`.)

Distinct from `../schemas/`, which holds tracked JSON Schema files for validating these configs.
