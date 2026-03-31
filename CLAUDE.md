# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Current Branch**: `feature/bulk-operations-and-api-enhancements` — main development branch with all features.

**PR Status (2026-03-30):** PR #19 submitted to alondmnt/joplin-mcp from `rebase/upstream-pr` branch. Awaiting review.

### Session Context (2026-03-30 — PR port session)

**What was done:**
- Ported all 12 MCP tools from monolithic fastmcp_server.py to alondmnt's v0.7.1 modular structure
- 3 clean commits: new files (3100 lines), required wiring (58 lines), optional enhancements (56 lines)
- Refactored field_helpers.py: removed 7 dead/buggy functions (extract_query_fields, build_conditional_fields_list, etc.), replaced with clean `_search_notes`, `_parse_update_params`, `ALL_NOTE_FIELDS`
- 87 unit tests (pr_tests.py) + live MCP testing of all 12 tools
- PR description at `PR_DESCRIPTION.md` (untracked, in repo root)

**Known issues to address:**
- `search_and_bulk_update_preview` missing `limit` parameter (Pydantic validation error when passed)
- Unit tests don't cover `search_and_bulk_update_preview/execute` MCP tools directly (only their helpers)
- `MANUAL_MCP_TEST_PLAN.md` has hardcoded note IDs from our test session — needs genericizing
- v1 files (`field_helpers_v1.py`, `notes_bulk_v1.py`) are untracked on rebase branch — delete when confident

**Branch notes:**
- `rebase/upstream-pr`: clean PR branch based on upstream v0.7.1 — do NOT commit project docs here
- `feature/bulk-operations-and-api-enhancements`: our full development branch — project CLAUDE.md lives here
- Session shutdown context capture must happen on the feature branch, not the PR branch

**See also:** `@CHANGELOG_FEATURE_ADDITIONS.md` for detailed feature additions and changes made to this fork.

## Project Background & Goals

This is a **fork of alondmnt's joplin-mcp** project, chosen for its comprehensive feature set and mature implementation. Our goals are to enhance it with:

### Fork Information

- **Original Repository**: https://github.com/alondmnt/joplin-mcp
- **Fork Point**: `d5a5daa` (docs: updated README) - Last alondmnt commit before our development branch
- **Current alondmnt HEAD**: `762e397` (fix: update Python version requirement in classifiers)

### Development Installation Commands

**Interactive Installation**:
```bash
cd /Users/mattheworlando/Documents/Projects/Code_Projects/joplin-mcp
source /Users/mattheworlando/miniforge3/etc/profile.d/conda.sh && conda activate joplin-mcp && python install.py
```

**Command-Line Installation**:
```bash
# Docker development (with environment token)
export JOPLIN_TOKEN="your_token_here"
python install.py --command-args --deployment docker --mode development

# Python production
python install.py --command-args --token "your_token_here" --deployment python --mode production
```

## PR Strategy and Future Development

### Contribution Split Strategy

**Upstream Sync Discovery (updated 2026-03-10)**: alondmnt has released v0.5.0 and v0.6.0 since our fork:
- **v0.5.0** (Jan 31): Path-based notebook resolution, `todo_due` param, search quoting fix (same as ours), single-note cache, **refactored monolithic `fastmcp_server.py` into modular `tools/` packages**, fixed `untag_note`
- **v0.6.0** (Feb 10): `edit_note` tool (find/replace, append, prepend without full-body overwrite), `find_in_note` (regex search within note), deletion tools disabled by default, docstring cross-references between `update_note` and `edit_note` for LLM tool selection
- **v0.7.0** (Mar): Claude Code plugin with Joplin orchestration skill, sorting for find functions, marketplace manifest
- **v0.7.1** (Mar): Bugfix — add `edit_note`/`import_from_file` to installer permission prompts
- **Merge complexity**: Higher than before — v0.5.0 refactored into `tools/notes.py` etc., so our PR must target their new modular structure, not the monolith
- **Overlaps**: Search quoting fix (both fixed independently), delete safety (different approaches)
- **Their gaps (our unique value)**: Bulk operations (6 tools), auto-backup revisions, `todo_completed` timestamp handling

**Recommended PR Approach**:

**Phase 1: Core Function Contributions (HIGH PRIORITY)**
- **Target**: Submit clean PR with our **6 new MCP tools** only:
  - `move_note`, `bulk_move_notes`, `bulk_tag_notes`, `strip_note_tags`
  - `search_and_bulk_update_preview`, `search_and_bulk_update_execute`
  - Enhanced `update_note` with full REST API parameters
- **Strategy**: Create `rebase/upstream-pr` from `upstream/main` (v0.6.0), port tools into their modular `tools/` structure
- **Benefits**: Clean, focused contribution with clear user value
- **Conflicts**: Minimal - these are primarily new function additions
- **Porting notes**: Tools slot into `tools/notes.py` and `tools/tags.py`. The field registry system (`JOPLIN_NOTE_FIELDS`, `generate_field_pars`) is self-contained infrastructure our bulk ops depend on — include as-is. `_save_note_revision()` auto-backup is a core safety contribution (adds `diff-match-patch` dependency). Skip: search quoting fix (they fixed independently). Delete safety enhancements (soft-delete verification, docstrings, restore) are complementary to his disable-by-default approach — candidate for a separate follow-up PR
- **PR etiquette**: First contact with alondmnt — include a note offering to restructure if preferred

**Porting Assessment (2026-03-28):**

alondmnt's v0.5.0+ modular structure (target for our PR):

| File | Contents |
|------|----------|
| `fastmcp_server.py` | Shared infra: validators, converters, client, pagination, search helpers |
| `formatting.py` | `ItemType` enum, `format_*_success`, pagination formatting |
| `content_utils.py` | Markdown parsing, TOC, previews, timestamps |
| `notebook_utils.py` | Notebook lookup by name/path, caching |
| `tools/notes.py` | All note tools (get, create, update, edit, delete, find, links) |
| `tools/notebooks.py` | Notebook CRUD |
| `tools/tags.py` | Tag CRUD + tag_note/untag_note |

Where our additions go:

| Our Addition | Target File | Difficulty |
|-------------|-------------|------------|
| `move_note`, `bulk_move_notes` | `tools/notes.py` | Low (additive) |
| `search_and_bulk_update_*` | `tools/notes.py` | Low (additive) |
| `bulk_tag_notes`, `strip_note_tags` | `tools/tags.py` | Low (additive) |
| `list_trash`, `restore_from_trash` | `tools/notes.py` or new `tools/trash.py` | Low (additive) |
| `get_note_history`, `restore_note_revision`, `manually_backup_note` | New `tools/revisions.py` | Low (new file) |
| `backup_database` | New `tools/backup.py` | Low (new file) |
| Field registry (`JOPLIN_NOTE_FIELDS`, `generate_field_pars`) | `fastmcp_server.py` | Medium (new infra) |
| `_save_note_revision` + diff helpers | Shared or `tools/revisions.py` | Medium (new infra + dependency) |
| `convert_todo_completed` | `fastmcp_server.py` | Low (extends converters) |
| `update_note` enhancements | `tools/notes.py` | **High** (both modified, merge required) |
| `format_delete_success` `soft_delete` param | `formatting.py` | Low (one-param addition) |

**Branch status**: `rebase/upstream-pr` exists, currently at `upstream/main` (now v0.7.1). Ready for porting.

**Current `upstream/main` HEAD**: `1a7f40e` (v0.7.1, fetched 2026-03-28)

**PR Principles:**
1. Adds our unique contributions (bulk ops, revisions, trash, backup)
2. Follows alondmnt's architecture, conventions, and patterns (his modular structure, his formatting helpers, his tool registration, his naming)
3. Doesn't duplicate or override things he's already solved (search quoting, `edit_note`, `find_in_note`, delete safety)
4. Minimizes diff surface — only add what's new, don't change what works

**PR Scope — all features we've developed:**
- 6 bulk operation tools: `move_note`, `bulk_move_notes`, `bulk_tag_notes`, `strip_note_tags`, `search_and_bulk_update_preview`, `search_and_bulk_update_execute`
- Enhanced `update_note` with full REST API parameters + `todo_completed` timestamp handling
- Field registry infrastructure (`JOPLIN_NOTE_FIELDS`, `generate_field_pars`, `apply_field_converters`)
- Safety: `_save_note_revision()` auto-backup with sequential diffs + `diff-match-patch` dependency
- Trash: `list_trash`, `restore_from_trash`
- Revisions: `get_note_history`, `restore_note_revision`, `manually_backup_note`
- Database backup: `backup_database` with auto-trigger before bulk ops
- `format_delete_success` `soft_delete` parameter

**Phase 2: MCP Docker Development Toolkit Extraction (SEPARATE PROJECT)**
- **Target**: Extract Docker development tooling into standalone `mcp-docker-dev` package
- **Vision**: Reusable development toolkit for ANY MCP project, not joplin-mcp specific
- **Key Features**:
  - Template-driven Docker setup (`Dockerfile.template`, `docker-compose.yml.template`)
  - Project auto-detection (parse `pyproject.toml` for package name/entry points)
  - Cross-platform networking fixes (host.docker.internal/localhost detection)
  - Hot-reload development environment with volume mounting
  - Port auto-assignment for multi-MCP development
  - Claude Desktop config template generation
- **Status**: See `DOCKER_DEV.md` for full development guide and extraction planning

**Benefits of Separation**:
- **Community Value**: Reusable across all MCP projects, not tied to Joplin
- **No Upstream Conflicts**: Completely separate from alondmnt's codebase
- **Focused Contributions**: Clean joplin-mcp PR without Docker complexity
- **Personal Utility**: Standardized development workflow across your MCP projects
- **Potential Impact**: Could become standard MCP development toolkit

### Branch Strategy and Workflow

This repository maintains three distinct workflows across different branches:

#### Branch Structure

**1. Main Development Branch: `feature/bulk-operations-and-api-enhancements`**
- **Purpose**: Primary development branch with ALL enhancements
- **Contains**:
  - 6 new MCP tools (move_note, bulk operations, search & update)
  - Docker development infrastructure
  - Enhanced installation system with deployment modes
  - Configuration management system
  - OS-aware networking fixes
  - All feature additions and improvements
- **Status**: This is YOUR enhanced joplin-mcp with full feature set
- **Preservation**: Keep intact - never rebase or clean this branch

**2. Clean PR Branch: `rebase/upstream-pr`**
- **Purpose**: Minimal, focused PR for upstream contribution
- **Based on**: `upstream/main` (alondmnt's latest)
- **Contains**: ONLY the 6 new MCP tools, cleanly integrated
- **Excludes**: Docker tooling, installation enhancements, config changes
- **Strategy**:
  - Create from fresh `upstream/main` checkout
  - Cherry-pick or manually add only MCP tool functions
  - Test against alondmnt's current architecture
  - Submit as focused PR to alondmnt/joplin-mcp
- **Benefits**: Minimal diff, easy review, high merge probability

**3. Docker Extraction (Separate Repository): `MatthewOGoodman/mcp-docker-dev`**
- **Purpose**: Extract Docker development toolkit as standalone project
- **Method**:
  - Fork `MatthewOGoodman/joplin-mcp` → `MatthewOGoodman/mcp-docker-dev` on GitHub
  - Create branch `extract/mcp-docker-dev` in new fork
  - Start with full joplin-mcp codebase (provides reference context)
  - Strip out Joplin-specific MCP tools and logic
  - Generalize Docker/installation infrastructure for any MCP project
  - Keep: Templates, auto-detection, networking fixes, deployment modes
  - Remove: Joplin API calls, note management, joplin-specific config
- **Benefits**:
  - Full git history available for reference during extraction
  - Independent repository for standalone toolkit
  - Can iterate without affecting joplin-mcp
  - Becomes reusable across all MCP projects

#### Workflow Summary

```
MatthewOGoodman/joplin-mcp
├── feature/bulk-operations-and-api-enhancements (keep all features)
└── rebase/upstream-pr (clean, from upstream/main + 6 tools only)
    → PR to alondmnt/joplin-mcp

MatthewOGoodman/mcp-docker-dev (forked from joplin-mcp)
└── extract/mcp-docker-dev (strip Joplin code, keep Docker toolkit)
    → Standalone MCP development toolkit
```

#### Execution Steps

1. ✅ **Preserve main development**: Keep `feature/bulk-operations-and-api-enhancements` unchanged
2. **Create clean PR branch**:
   ```bash
   git fetch upstream
   git checkout -b rebase/upstream-pr upstream/main
   # Add only 6 new MCP tools
   # Test and submit PR
   ```
3. **Fork for extraction**: Fork joplin-mcp → mcp-docker-dev on GitHub
4. **Extract Docker toolkit**:
   ```bash
   git clone https://github.com/MatthewOGoodman/mcp-docker-dev.git
   cd mcp-docker-dev
   git checkout -b extract/mcp-docker-dev
   # Remove Joplin-specific code
   # Generalize Docker/installation infrastructure
   # Create templates and documentation
   ```

#### Why This Approach Works

- ✅ **No data loss**: Main branch preserves all work
- ✅ **Clean upstream contribution**: Minimal, focused PR
- ✅ **Version controlled extraction**: Full history for reference
- ✅ **Independent projects**: Each serves different purpose
- ✅ **Easy maintenance**: Clear separation of concerns

#### Final Validation

Before submitting PR and publishing Docker toolkit:

1. **Verify Joplin MCP functions work correctly on rebased upstream code**
   - Test all 6 new MCP tools against alondmnt's current architecture
   - Ensure no breaking changes from upstream updates
   - Validate function signatures match expected API

2. **Ensure Docker toolkit works independently across different MCP projects**
   - Test extraction against minimal "hello world" MCP server
   - Verify templates work with different project structures
   - Validate cross-platform compatibility (macOS/Linux/Windows)

3. **Submit clean Joplin MCP function PR to alondmnt's upstream**
   - Ensure minimal diff (only 6 new tools)
   - Include tests and documentation
   - Follow alondmnt's contribution guidelines

### TODO: Enhanced Notebook Hierarchy Management

**Issue**: Current `update_notebook()` function only supports title updates, but Joplin supports hierarchical notebook organization via `parent_id` field.

**Proposed Enhancement**: Add notebook hierarchy management to `update_notebook()`:
- Add `parent_id` parameter for moving notebooks between hierarchies
- Add `parent_notebook` parameter for user-friendly notebook name references
- Support creating nested notebook structures
- Handle top-level notebooks (parent_id = NULL) vs nested notebooks

**Use Cases**:
- `update_notebook(notebook_id, title="New Name", parent_notebook="Projects")` - Rename and move to parent
- `update_notebook(notebook_id, parent_notebook="")` - Move to top-level
- Enable complex notebook reorganization workflows

**Benefits**:
- Complete notebook management capabilities
- Consistent with note movement API design
- Enables hierarchical organization workflows

### COMPLETED: Fix todo_completed Timestamp Handling

`todo_completed` now writes proper epoch-ms timestamps via `convert_todo_completed()`. Accepts `True/False` (current time), epoch milliseconds, or ISO datetime strings (`YYYY-MM-DD HH:MM`, `YYYY-MM-DD`). Auto-sets `is_todo=True` when marking complete; raises error if `is_todo=False` with truthy completion. See `markdowns/plans_completed/COMPLETED_TODOS.md` for full implementation details.

### TODO: Prioritized New Functionality

**Tier 1: Safety and Data Protection (HIGHEST PRIORITY)**

Joplin's Web Clipper API has no undo. Note revisions exist but store diffs, not snapshots. Current write operations have no backup or confirmation mechanisms.

- ~~**Auto-backup before note modification**~~: **COMPLETED** — Uses Joplin's native revision system via `POST /revisions` with diff-match-patch. Before any `update_note` or `search_and_bulk_update_execute` body overwrite, `_save_note_revision()` snapshots the current note content as a revision. Restorable from Joplin Desktop's built-in "Note History" UI (restores to "Restored Notes" notebook). Key details: JSON diff-match-patch format (patches from `""` → current content), `metadata_diff` as `{"new": {...}, "deleted": []}`, millisecond timestamps (joppy's `add_revision` has a seconds bug — bypassed with `client.post()` directly). `diff-match-patch` added as dependency.
- ~~**Fix `_save_note_revision()` to use sequential diffs**~~: **COMPLETED** — Now matches Joplin's `createNoteRevision_` algorithm: checks for latest parent revision, reconstructs previous state, creates sequential diff with `parent_id`. Only diffs from `""` for first revision of a note.
- ~~**`manually_backup_note`**~~: **COMPLETED** — Exposed `_save_note_revision()` as MCP tool for user-triggered snapshots before risky manual edits
- ~~**`restore_note_from_backup`**~~: **COMPLETED** — Implemented as `restore_note_revision` MCP tool (programmatic restore from revision diffs). Also available via Joplin Desktop's "Note History" UI.
- ~~**Fix `delete_note` to use soft-delete**~~: **COMPLETED** — Verified empirically: `delete_note` and `delete_notebook` already soft-delete to trash (restorable from Joplin Desktop). `delete_tag` is permanent (tags have no trash). Updated docstrings, return messages, and safety annotations. `permanent=1` API parameter intentionally NOT exposed.
- ~~**`list_trash`**~~: **COMPLETED** — Lists soft-deleted notes/notebooks with deletion date and original notebook name
- ~~**`restore_from_trash`**~~: **COMPLETED** — Restores trashed note/notebook by setting `deleted_time` to 0. If original notebook was also trashed, restores to it (restore notebook first for visibility)
- ~~**`get_note_history`**~~: **COMPLETED** — Lists revisions for a note with timestamps, titles (extracted from both JSON and legacy diff formats), and parent chain info
- ~~**`restore_note_revision`**~~: **COMPLETED** — Reconstructs note content by walking the revision parent chain and applying diffs sequentially. Creates a new note with restored content (same as Joplin Desktop behavior). Supports both Joplin auto-saved and MCP-created revisions.
- ~~**Full database backup strategy**~~: **COMPLETED** — `backup_database` MCP tool creates SQLite snapshots via `sqlite3 .backup` (~98MB, <1s). Auto-triggered before `search_and_bulk_update_execute` and `bulk_move_notes` with once-per-day guard. Manual tool bypasses guard. Backups stored in `~/JoplinBackup/default/mcp-backups/`, last 10 retained. Restore: copy backup over `~/.config/joplin-desktop/database.sqlite` while Joplin Desktop is closed.

**Tier 2: Organization Enhancements**

- **Enhanced notebook hierarchy** (see TODO above): Add `parent_id`/`parent_notebook` to `update_notebook()` for moving notebooks between hierarchy levels
- **`get_recent_changes`**: Expose Joplin's events API — activity feed showing recent creates/updates/deletes with timestamps
- **`find_in_note`**: Search within a specific note (alondmnt added this upstream — consider integrating)
**Tier 3: Advanced Search**

- **Document Joplin search operators** in MCP tool descriptions: `title:`, `body:`, `tag:`, `notebook:`, `created:`, `updated:`, `due:`, `type:`, `iscompleted:`, `resource:`, `sourceurl:`, `any:1` (OR), `-` (negation), `*` (wildcard)
- **Search helper or query builder**: Assist users in constructing complex Joplin search queries

**Tier 4: Resource and Attachment Management**

- **`list_resources`** / **`get_note_resources`**: List attachments globally or per-note
- **`get_resource`**: Get attachment metadata, including OCR-extracted text from images/PDFs
- **`upload_resource`**: Attach files to notes
- **`delete_resource`**: Remove attachments

## MCP Configuration Management System

### **Overview**

The `mcp-config-manager.sh` script provides seamless switching between different joplin-mcp deployment modes while preserving all MCP server configurations and handling Claude Desktop resets.

### **Available Deployment Modes**

```bash
./mcp-config-manager.sh docker-dev      # Development with live code changes
./mcp-config-manager.sh docker-prod     # Production Docker deployment  
./mcp-config-manager.sh python-uvx      # Quick deployment testing (zero-install)
./mcp-config-manager.sh python-installed # Installed Python package
```

### **Management Commands**

```bash
./mcp-config-manager.sh backup          # Backup current configurations
./mcp-config-manager.sh restore [file]  # Restore from backup (latest if no file)
./mcp-config-manager.sh status          # Show current status and server counts
```

### **Entry Point Strategy**

- **Development**: `docker-dev` → `run_fastmcp_server.py` (enhanced CLI options)
- **Package Testing**: `python-uvx` → `uvx joplin-mcp` (quick deployment validation)
- **Production**: `docker-prod`, `python-installed` → `joplin_mcp.server` (official entry points)

### **Key Features**

- **Smart Backup System**: Timestamped backups with validation (stored in `~/.mcp-config-backups/`)
- **Token Management**: Automatic JOPLIN_TOKEN extraction from backups or environment
- **Configuration Merging**: Preserves other MCP servers (kagi, etc.) during switches
- **Claude Desktop Reset Recovery**: Full restoration after app resets
- **Server Count Validation**: Reports MCP server counts for current configs and backups
- **Cross-Platform**: Supports macOS, Linux, and Windows Claude Desktop paths

## Development Commands

### Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src/joplin_mcp --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py

# Run integration tests only
pytest -m integration

# Run without slow tests
pytest -m "not slow"
```

**Joplin MCP manual testing**: Use the **"Testing"** notebook in Joplin for creating test notes, tags, and other items during MCP tool development and verification.

### Code Quality

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type checking
mypy src/

# Run all quality checks
black src/ tests/ && ruff check src/ tests/ && mypy src/
```

### Development Setup

**Editable install** (`pip install -e .`) is used so code edits take effect on MCP server reload
without reinstalling.

**macOS permissions requirement**: `python3.13` needs **Full Disk Access** (System Settings >
Privacy & Security > Full Disk Access). Claude Desktop spawns python as a subprocess, and macOS
TCC permissions don't propagate from parent to child. Without this, python3.13 gets
`[Errno 1] Operation not permitted` reading from the source tree within `~/Documents/.../joplin-mcp`. This was the cause of editable
installs appearing "broken" — the install itself was fine, but the subprocess couldn't read the
source tree.

**Dev workflow** (edit code, reload, test — no pip install or app restart):
1. Edit source files in `src/joplin_mcp/`
2. In Claude Desktop: **Developer > Reload MCP Configuration**
3. Changes are live

```bash
# Install with dev dependencies (editable)
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Test server locally
python run_fastmcp_server.py

# Run CLI commands
joplin-mcp-server
joplin-mcp-install
```

### **alondmnt's Original Flow (No Deployment Awareness)**

**Functions in Sequence**:
1. **`run_installation_process(config_path_resolver, is_development, ...)`** - Main orchestrator, only knows `is_development` from caller
2. **`config_path_resolver(token)`** - Calls `create_joplin_config(token)`
3. **`create_joplin_config(token)`** (install.py) - Wrapper function
4. **`JoplinMCPConfig.create_interactively(token, **DEFAULT_CONNECTION)`** - Creates config object with hardcoded defaults
5. **`config.save_interactively(config_path)`** - Saves to joplin-mcp.json
6. **`update_chat_interface_config(interface_name, config_path, is_development)`** - Updates Claude Desktop config
7. **`interface.create_mcp_config(config_path, is_development)`** - Creates MCP server config
8. **`create_base_mcp_config(config_path, is_development)`** - Reads joplin-mcp.json via `get_joplin_environment_variables()`

**Key Insight**: alondmnt had NO deployment type selection. The `is_development` parameter just came from the calling script.

### **Our Actual Implemented Flow (Dual-Path Architecture)**

**Enhanced Installation Process with Parallel Command-Line Support**:

**Path A: Interactive Flow (Enhanced alondmnt Flow)**:
1. **`main()`** (install.py) - Parses args, routes to interactive or command-line flow
2. **`run_installation_process(config_path_resolver, is_development, ...)`** - Enhanced orchestrator with deployment awareness
3. **`get_token_interactively()`** - Gets Joplin API token (unchanged from alondmnt)
4. **`config_path_resolver(token)`** - Calls `create_joplin_config(token)` (unchanged)
5. **`JoplinMCPConfig.create_interactively(token, **DEFAULT_CONNECTION)`** - Creates config object (unchanged)
6. **`config.save_interactively(config_path)`** - Saves to joplin-mcp.json (unchanged)
7. **NEW: `get_deployment_choice()`** - User selects "python" or "docker" deployment
8. **NEW: `get_mode_choice()`** - User selects development (True) or production (False) mode
9. **NEW: `prepare_docker_deployment(config_path)`** - If docker selected, builds Docker images and validates environment
10. **`update_chat_interface_config(interface_name, config_path, is_development, deployment_type)`** - Enhanced with deployment_type parameter
11. **`interface.create_mcp_config(config_path, is_development, deployment_type)`** - Enhanced Claude Desktop config creation
12. **`create_base_mcp_config_new(config_path, is_development, deployment_type)`** - Enhanced with OS-aware Docker networking fixes

**Path B: Command-Line Flow (Parallel Non-Interactive)**:
1. **`main()`** (install.py) - Detects command-line args via `has_command_args(args)`
2. **`run_command_line_installation(args)`** - Parallel implementation bypassing alondmnt's interactive flow
3. **Token resolution**: `args.token or os.environ.get("JOPLIN_TOKEN")` - CLI arg > env var > error
4. **`create_command_line_config(token, deployment_type)`** - Direct JoplinMCPConfig constructor with OS-aware host selection
5. **`config.save_interactively(config_path)`** - Reuses alondmnt's save method (includes token)
6. **Docker preparation**: If deployment_type == "docker", calls Docker build and validation
7. **`update_chat_interface_config(interface_name, config_path, is_development, deployment_type)`** - Same enhanced function as interactive flow

**Key Implementation Details**:
- **Deployment Type Awareness**: Both flows now pass `deployment_type` ("python"|"docker") through the entire chain
- **OS-Aware Docker Networking**: `create_command_line_config()` and `create_base_mcp_config_new()` apply `host.docker.internal` fix for macOS/Windows Docker deployments
- **Docker Infrastructure**: Automatic Docker image building, container cleanup, and environment validation
- **Parallel Architecture**: Command-line flow completely bypasses interactive prompts while reusing core alondmnt functions
- **Template-Based Configuration**: Enhanced `create_base_mcp_config_new()` uses deployment templates instead of hardcoded values
- **Mode Switching Integration**: Both flows integrate with existing `switch_mode.py` for post-installation deployment changes

## Architecture Overview

This is a **FastMCP-based Model Context Protocol (MCP) server** that provides AI assistants access to Joplin notes through 27 standardized tools.

### Core Components

- **`src/joplin_mcp/fastmcp_server.py`** - Main FastMCP server implementation with all 27 tools and Pydantic validation
- **`src/joplin_mcp/config.py`** - Configuration management supporting JSON, YAML, and environment variables
- **`src/joplin_mcp/server.py`** - Legacy server implementation
- **`run_fastmcp_server.py`** - Server launcher supporting both STDIO and HTTP transports

### Tool Categories (33 tools)

**Read-only (13 tools):**
- **System**: `ping_joplin`
- **Note Retrieval**: `get_note` (smart TOC/section/line reading), `get_links` (outgoing + backlinks)
- **Note Finding and Search**: `find_notes`, `find_notes_with_tag`, `find_notes_in_notebook`, `get_all_notes`
- **Notebook and Tag Listing**: `list_notebooks`, `list_tags`, `get_tags_by_note`
- **Bulk Preview**: `search_and_bulk_update_preview`
- **Trash**: `list_trash` (list soft-deleted notes/notebooks)
- **History**: `get_note_history` (list revisions for a note)

**Write operations (16 tools):**
- **Note Management**: `create_note`, `update_note` (partial field update), `delete_note` (soft-delete to trash), `move_note`
- **Bulk Operations**: `bulk_move_notes`, `search_and_bulk_update_execute` (requires preview first), `strip_note_tags`
- **Notebook Management**: `create_notebook`, `update_notebook` (title only), `delete_notebook` (soft-delete to trash, including contained notes)
- **Tag Management**: `create_tag`, `update_tag`, `delete_tag` (**PERMANENT** — tags have no trash), `tag_note`, `untag_note`, `bulk_tag_notes`
- **Trash Recovery**: `restore_from_trash` (restore soft-deleted note or notebook)
- **Revision Recovery**: `restore_note_revision` (reconstruct note from revision diffs), `manually_backup_note` (create on-demand revision snapshot)

**Safety status of write operations:**
- `update_note`: Partial update (only specified fields change), auto-backup revision before title/body overwrite
- `delete_note`: Soft-delete — moves to Joplin's trash, restorable from Joplin Desktop
- `delete_notebook`: Soft-delete — moves notebook and contained notes to trash, restorable
- `delete_tag`: **Permanent deletion** — tags do NOT use Joplin's trash system, cannot be restored
- `search_and_bulk_update_execute`: Has preview/confirm pattern (safest write operation)
- All other writes: No confirmation, no undo
- **Note:** `permanent=1` API parameter exists but is intentionally NOT exposed — all note/notebook deletes go to trash

### Joplin API Discoveries (Unexposed Capabilities)

The Joplin REST API and `joppy` Python library support significant capabilities not yet exposed through MCP tools:

**1. Trash/Soft-Delete System** — `DELETE /notes/:id` soft-deletes by default (sets `deleted_time`). Only `DELETE /notes/:id?permanent=1` permanently deletes. **Verified**: our `delete_note` and `delete_notebook` correctly soft-delete (no `permanent=1` passed). Tags have no trash system — `delete_tag` is permanent. Trashed items can be listed (`include_deleted=1`) and restored (set `deleted_time` to 0). `permanent=1` is intentionally NOT exposed in our MCP tools.

**2. Note Revision History** — Joplin auto-saves note versions every 10 minutes, retained 90 days. Revisions stored as diffs (diff-match-patch format). `joppy` has `get_all_revisions()`, `get_revision()` etc. — completely unused. Reconstructing full content from diffs requires applying them sequentially (no direct "get version N" API — there's an open Joplin forum request for this).

**3. Resource/Attachment Management** — Complete CRUD for attachments: list, get metadata, download file content, upload, delete. Also supports OCR text extraction from images/PDFs. `joppy` exposes all of these — completely unused.

**4. Events/Change Tracking** — Activity feed API: recent creates/updates/deletes with timestamps, cursor-based pagination, 90-day retention. Useful for monitoring and audit trails.

**5. Advanced Search Operators** — Joplin search supports operators not documented in MCP tool descriptions: `title:`, `body:`, `tag:`, `notebook:`, `created:`, `updated:`, `due:`, `type:`, `iscompleted:`, `resource:`, `sourceurl:`, `any:1` (OR logic), `-` (negation), `*` (wildcard).

### Configuration System

- **Primary**: JSON files (`joplin-mcp.json`)
- **Alternative**: YAML files or environment variables
- **Tool Permissions**: Granular control over create/update/delete operations
- **Privacy Controls**: Content exposure settings (none/preview/full)
- **Transport Options**: STDIO (default) or HTTP

### Dependencies

- **FastMCP**: Core MCP server framework
- **joppy**: Python client for Joplin REST API
- **Pydantic**: Data validation and type safety
- **httpx**: HTTP client for Joplin API communication

### Key Patterns

- All tools use Pydantic models for input validation
- Configuration supports hierarchical loading (env vars → files → defaults)
- Error handling with detailed user feedback
- Tool permissions controlled via configuration
- Support for both development and production deployments