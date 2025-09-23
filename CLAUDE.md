# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

**Upstream Sync Discovery**: After fetching `upstream/main`, alondmnt has been actively developing:
- **New commits since fork**: `762e397..c8022cb` (6 commits including HTTP transport features and `find_in_note` tool)
- **Merge complexity**: Extensive conflicts across core files (`fastmcp_server.py`, config, Docker, README)
- **Architectural differences**: Our STDIO development tooling vs alondmnt's HTTP production approach

**Recommended PR Approach**:

**Phase 1: Core Function Contributions (HIGH PRIORITY)**
- **Target**: Submit clean PR with our **6 new MCP tools** only:
  - `move_note`, `bulk_move_notes`, `bulk_tag_notes`, `strip_note_tags`
  - `search_and_bulk_update_preview`, `search_and_bulk_update_execute`
  - Enhanced `update_note` with full REST API parameters
- **Strategy**: Cherry-pick/rebase tool additions onto `upstream/main`
- **Benefits**: Clean, focused contribution with clear user value
- **Conflicts**: Minimal - these are primarily new function additions

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

### TODO: Separate Todo Timestamp vs Boolean Parameters

**Issue**: Current parameter design conflates timestamp and boolean semantics for `todo_completed`:
- **API Field**: `todo_completed` expects timestamp (milliseconds when completed)  
- **Filter Logic**: `todo_completed_filter` needs boolean (completed vs incomplete)
- **Current Problem**: Cannot do early parameter conversion without losing timestamp information

**Proposed Solution**: Split into separate parameters:
- `todo_completed_time` - timestamp for setting completion time (PUT operations)
- `completed` - boolean for filtering/search logic (replaces `todo_completed_filter`)
- `completed_filter` - boolean filter parameter (consistent with naming)

**Benefits**:
- Clear separation of timestamp vs boolean semantics
- Enables early parameter conversion without data loss
- More intuitive API for users
- Consistent with Joplin's internal distinction between completion timestamp and completion status


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
```bash
# Install in development mode with dev dependencies
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

### Tool Categories

1. **Note Finding & Search** (5 tools): find_notes, find_notes_with_tag, find_notes_in_notebook, get_all_notes, get_note
2. **Note Management** (6 tools): create_note, update_note, delete_note, get_links, move_note, strip_note_tags
3. **Notebook Management** (4 tools): list_notebooks, create_notebook, update_notebook, delete_notebook
4. **Tag Management** (8 tools): list_tags, create_tag, update_tag, delete_tag, get_tags_by_note, tag_note, untag_note, bulk_tag_notes
5. **Bulk Operations** (3 tools): bulk_move_notes, search_and_bulk_update_preview, search_and_bulk_update_execute
6. **System** (1 tool): ping_joplin

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


