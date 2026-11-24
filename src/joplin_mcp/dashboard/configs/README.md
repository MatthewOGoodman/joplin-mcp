# configs/

Gitignored dir (contents). Holds symlinks to consumer dashboard YAML config files.

Each entry is a symlink pointing into the owning consumer repo, e.g.:

```
configs/job_search.yaml -> ~/projects/dev/job_search/dashboards/job_search.yaml
```

`joplin-dashboard <name>` does symlink-discovery here: a bare name (no path separator, no `.yaml` extension) such as `joplin-dashboard job_search` resolves `configs/job_search.yaml` and renders against it. A broken symlink is reported as a clean error.

Distinct from `../schemas/`, which holds tracked JSON Schema files for validating these configs.
