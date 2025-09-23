# Changes and Feature Additions

This document summarizes the enhancements made to the joplin-mcp project, organized by feature area.

## Enhanced MCP Tools (6 New Tools Added)

The server now provides **27 tools** (up from 21), with significant improvements to note management capabilities:

### New Functions
- **`move_note(note_id, target_notebook="Archive")`** - Move single note between notebooks (supports notebook names)
- **`bulk_move_notes(note_ids, target_notebook="Archive")`** - Move multiple notes to target notebook (supports notebook names)
- **`bulk_tag_notes(note_ids, tag_names)`** - Apply multiple tags to multiple notes
- **`strip_note_tags(note_id)`** - Remove all tags from a single note
- **`search_and_bulk_update_preview(query, parent_notebook="Archive")`** - Preview bulk operations with safety verification
- **`search_and_bulk_update_execute(query, expected_count, first_title, parent_notebook="Archive")`** - Execute bulk updates safely with confirmation

### Enhanced Functions
- **`update_note()`** - Extended with full REST API support including `parent_id` field and user-friendly `parent_notebook` parameter

### Bulk Update Workflow
Safe bulk operations with mandatory preview and verification:
1. **Preview**: `search_and_bulk_update_preview("project")` → See total count + sample notes + content
2. **Execute**: `search_and_bulk_update_execute("project", 47, "Project Meeting", parent_id="abc123def456")` → Bulk move with safety verification

### Usage Examples
- **Single move**: `move_note("note123", target_notebook="Archive")` → Move one note using notebook name
- **Batch move**: `bulk_move_notes(["note1", "note2", "note3"], target_notebook="Archive")` → Move multiple notes using notebook name
- **Content + Move**: `update_note("note123", title="Archived Item", parent_notebook="Archive")` → Update and move using notebook name
- **Tag Cleanup**: `strip_note_tags("note123")` → Remove all tags from note

## Docker Development Tooling

Development workflow improvements with containerized STDIO deployment:

### Development Docker Pipeline
- **Multi-stage Dockerfile** with development and production targets for STDIO transport
- **Hot-reload development environment** with volume mounting for live code changes during development
- **Containerized STDIO deployment** - Same Claude Desktop transport, containerized for consistency
- **Comprehensive Makefile** with build, run, test, and cleanup targets
- **docker-compose.yml template** - Infrastructure foundation for future expansion

### Cross-Platform Docker Networking
- **Automatic OS detection** for Docker networking configuration
- **macOS/Windows support** using `host.docker.internal` for Docker Desktop environments
- **Linux compatibility** using `localhost` for native Docker environments
- **Dynamic application** of OS fixes during config creation and mode switching

### Development Benefits
- **Faster development iteration** with hot-reload capabilities
- **Consistent deployment environment** across development and production
- **Simplified development setup** with automated build and cleanup processes

## Installation and Configuration Enhancements

### Command-Line Installation
Non-interactive installation flow alongside existing interactive mode:

```bash
# Interactive installation (original)
python install.py

# Command-line installation (new)
export JOPLIN_TOKEN="your_token_here"
python install.py --command-args --deployment docker --mode development

# Python production
python install.py --command-args --token "your_token_here" --deployment python --mode production
```

### Mode Switching System
New `switch_mode.py` script with automated deployment switching:

```bash
# Non-interactive mode switching (automation-friendly)
python -m src.joplin_mcp.switch_mode --mode dev   # Switch to development mode
python -m src.joplin_mcp.switch_mode --mode prod  # Switch to production mode

# Interactive mode selection (user-friendly)
python -m src.joplin_mcp.switch_mode              # Prompts for mode choice

# Advanced deployment override
python -m src.joplin_mcp.switch_mode --mode dev --deployment docker
```

#### Key Features
- **Automatic deployment detection** - Always detects and defaults to current deployment type
- **Smart confirmation** - Dev→prod confirmation only in interactive mode, silent for command-line
- **Template integration** - Leverages template-based configuration system

### Deployment Template System
Four deployment modes with template-based configuration:

- **joplin-python-installed**: Production Python package deployment
- **joplin-python-uvx**: Quick testing with uvx (zero-install)
- **joplin-docker-dev**: Development Docker with volume mounts
- **joplin-docker-prod**: Production Docker with self-contained code

### Configuration Management
Enhanced token and configuration flow:
- **Orthogonal systems** - Token management and deployment switching are completely independent
- **Environment variable fallback** - `joplin-mcp.json` with `token: null` correctly triggers `JOPLIN_TOKEN` env var fallback
- **Template substitution** - Uses `${VARIABLE}` placeholders resolved at runtime
- **Cross-platform paths** - Dynamic PROJECT_ROOT calculation works for any user's system

## Multi-MCP Infrastructure (Template Foundation)

### Development Infrastructure
- **docker-compose.yml template** - Foundation for future multi-MCP deployments with port-based separation
- **Multi-stage Docker pipeline** - Supports both development and production containerization approaches
- **Template-based configuration** - Infrastructure for deployment mode switching

### Current Scope
- **Active transport**: STDIO (fully operational with Claude Desktop)
- **Infrastructure status**: Template and build foundation established for future HTTP/SSE multi-MCP expansion
- **Note**: HTTP/SSE transport server implementation available in codebase (alondmnt's original work) but not utilized in current deployment workflow

## API Design Philosophy

### Safety-First Bulk Operations
- **No generic bulk_update_note()** function by design
- **Mandatory safety verification** - All bulk updates must use `search_and_bulk_update_*()` with preview and confirmation
- **Prevents accidental bulk modifications** without explicit verification steps

### Function Usage Guidelines
- **Content Updates**: Use `update_note()` for general-purpose updates including content, metadata, and movement
- **Move-Only Operations**: Use dedicated `move_note()` and `bulk_move_notes()` for clearer intent
- **Tag Operations**: Use `tag_note()` for single operations and `bulk_tag_notes()` for batch operations

## Installation Requirements

### Docker Requirements
- **Joplin Desktop** running with Web Clipper enabled
- **JOPLIN_TOKEN** from Joplin Desktop → Tools → Options → Web Clipper → Authorization token
- **Network access** to localhost:41184 (Joplin web clipper port)
- **Docker installed** for containerized deployments

### Python Requirements
- **Python 3.8+**
- **Dependencies**: FastMCP, joppy, pydantic, httpx, PyYAML
- **Optional**: uvx for zero-install testing

## Technical Architecture

### Core Components
- **FastMCP-based server** with 27 standardized tools and Pydantic validation
- **Configuration management** supporting JSON, YAML, and environment variables
- **Cross-platform compatibility** with OS-aware networking
- **Template-based deployment** system

### Dependencies
- **FastMCP**: Core MCP server framework
- **joppy**: Python client for Joplin REST API
- **Pydantic**: Data validation and type safety
- **httpx**: HTTP client for Joplin API communication

## Credits

Docker Make pipeline implementation inspired by [JPFrancoia/jopmcp](https://github.com/JPFrancoia/jopmcp).

This enhancement maintains full backward compatibility with the original joplin-mcp implementation while adding significant new capabilities for bulk operations, Docker deployment, and automation.