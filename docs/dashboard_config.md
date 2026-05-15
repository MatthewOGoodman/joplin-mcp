# Dashboard config — format spec

This is the canonical key-by-key reference for the YAML configs consumed by `joplin-dashboard`. Configs are validated against `src/joplin_mcp/dashboard/schemas/dashboard_config.schema.yaml` at load time; unknown keys are rejected.

The schema is the machine-readable contract; this doc is its human-readable companion. They are hand-kept-in-sync; a unit test extracts the canonical example below and asserts it validates against the schema.

## Top-level keys

| Key | Type | Required | Default | Description |
|---|---|---|---|---|
| `output` | string (path) | yes | — | Where to write the rendered dashboard. Tilde-expanded; parent dirs auto-created. |
| `sections` | array | yes | — | One or more section definitions. Order in the file = order in the output. |
| `header` | string | no | `""` | Markdown rendered before the first section. May contain `{timestamp}` placeholder. |
| `footer` | string | no | `""` | Markdown rendered after the last section. |

Unknown top-level keys are rejected (`additionalProperties: false`).

## Section keys

| Key | Type | Required | Default | Description |
|---|---|---|---|---|
| `title` | string | yes | — | Heading rendered above the section's table. |
| `notebook` | string \| null | no | `null` | Notebook name (leaf, not path — see "Notebook paths" below) to scope the section's query. Omit or `null` to search all notebooks. |
| `tags_required` | array of strings | no | `[]` | Tags ALL of which a note must have to appear. |
| `tags_excluded` | array of strings | no | `[]` | Tags ANY of which excludes a note. |
| `extra_query` | string \| null | no | `null` | Raw search-syntax appended to the constructed query. |
| `columns` | array of strings | no | `["title", "updated"]` | Column names rendered in the table, left-to-right. See "Columns" below. |
| `group_by_tag_prefix` | string \| null | no | `null` | If set, the section is split into sub-sections keyed by the suffix of tags starting with this prefix. |
| `sort_by` | string | no | `"updated"` | Sort column. Either a built-in (`title`, `updated`, `created`, `notebook`) or a frontmatter field name. |
| `sort_dir` | string | no | `"desc"` | Sort direction. `"asc"` or `"desc"`. |

Unknown section keys are rejected.

## Columns

`columns` is a free-form array of strings. Each string is either:

1. **A built-in column** — one of: `title`, `tags`, `notebook`, `updated`, `created`, `id`.
2. **A frontmatter field name** — any other string; resolves against the YAML frontmatter of each note. Renders empty if the field is absent.

The schema cannot distinguish these (both are strings); built-ins are documented here but not enumerated in the schema, since rejecting unknown column names would break frontmatter passthrough.

## Notebook paths

The current `notebook` field is matched against the leaf name only (e.g., `"People"` matches `1-Job Search/People`). Full-path matching is a tracked open feature; consumer configs use leaf names today.

## Validation behavior

- The CLI validates the config before any Joplin REST calls.
- Multiple errors are surfaced in one pass; the CLI prints each with a JSON Pointer path (e.g., `/sections/0/sort_dir: 'foo' is not one of ['asc', 'desc']`) and exits with code 2.
- Use `joplin-dashboard --validate <config>` to run validation without rendering.

## Canonical example

The block below is the canonical example. It is consumed by the unit test `test_canonical_example_validates`; if the schema or this doc drifts, that test fails. Keep the example minimal but exercising every documented key.

<!-- canonical-example -->
```yaml
output: ~/projects/dev/job_search/DASHBOARD.md

header: |
  # Job Search Dashboard
  _Auto-generated. Last refresh: {timestamp}_

footer: ""

sections:
  - title: "People — active"
    notebook: "People"
    tags_required: ["Job: Status: Active"]
    tags_excluded: []
    extra_query: null
    columns: [title, tags, updated]
    group_by_tag_prefix: null
    sort_by: updated
    sort_dir: desc

  - title: "Applications by phase"
    notebook: "Applications"
    tags_excluded: ["Job: Status: Archived"]
    group_by_tag_prefix: "Job: Phase "
    columns: [title, tags, priority, updated]
    sort_by: updated
    sort_dir: desc
```
<!-- /canonical-example -->

The second section above demonstrates frontmatter passthrough — `priority` is not a built-in column; it resolves against each note's YAML frontmatter.
