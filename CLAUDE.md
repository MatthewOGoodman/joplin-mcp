# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Background & Goals

This is a **fork of alondmnt's joplin-mcp** project, chosen for its comprehensive feature set and mature implementation. Our goals are to enhance it with:

### Current Enhancement Goals

1. **Enhanced PUT API Support**: 
   - Improve `update_note()` to support changing the `parent_id` field
   - Enable moving notes between notebooks seamlessly
   - Add batch move operations for workflow efficiency

2. **Docker Make Pipeline**:
   - Port the Docker Make pipeline from our previous jopmcp implementation
   - joplin-mcp has Docker deployment but lacks the Make pipeline workflow

### Reference Implementation Context

The `ref_jopmcp_fork/` directory contains our previous work on a simpler **jopmcp** implementation that informed these enhancement goals:

- **jopmcp Implementation**: 10 tools, basic CRUD operations, complete Docker Make pipeline
- **Key jopmcp Strengths**: Docker support with Makefile (`make pkg`, `make server`, `make client`)
- **Key jopmcp Gaps**: Missing DELETE operations, limited tag management
- **Strategy**: Adopt alondmnt's mature joplin-mcp (21 tools, complete CRUD) and port our Docker Make pipeline

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

## Architecture Overview

This is a **FastMCP-based Model Context Protocol (MCP) server** that provides AI assistants access to Joplin notes through 21 standardized tools.

### Core Components

- **`src/joplin_mcp/fastmcp_server.py`** - Main FastMCP server implementation with all 21 tools and Pydantic validation
- **`src/joplin_mcp/config.py`** - Configuration management supporting JSON, YAML, and environment variables
- **`src/joplin_mcp/server.py`** - Legacy server implementation
- **`run_fastmcp_server.py`** - Server launcher supporting both STDIO and HTTP transports

### Tool Categories

1. **Note Finding & Search** (5 tools): find_notes, find_notes_with_tag, find_notes_in_notebook, get_all_notes, get_note
2. **Note Management** (4 tools): create_note, update_note, delete_note, get_links
3. **Notebook Management** (4 tools): list_notebooks, create_notebook, update_notebook, delete_notebook
4. **Tag Management** (7 tools): list_tags, create_tag, update_tag, delete_tag, get_tags_by_note, tag_note, untag_note
5. **System** (1 tool): ping_joplin

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

## Enhancement Implementation Status

### ✅ Phase 1: Enhanced Note Movement (COMPLETED)
- **Enhanced `update_note()` function** - Added all REST API parameters including `parent_id`, GPS coordinates, timestamps, etc.
- **Implemented `bulk_move_notes()`** - Batch move multiple notes between notebooks with detailed error reporting
- **Added `search_and_bulk_update_preview()`** - Three-level preview system (count + metadata + content inspection)
- **Added `search_and_bulk_update_execute()`** - Safe bulk updates with verification and all update_note parameters

### Phase 2: Docker Integration (Priority: High)  
- Port multi-stage Dockerfile from ref_jopmcp_fork/
- Add Docker Makefile targets (pkg, run, dev)
- Configure environment variables for container deployment
- Test both development and production container builds

### Phase 3: Additional Enhancements (Priority: Medium)
- Enhanced error handling for move operations
- Validation for parent_id relationships
- Performance optimization for bulk operations
- Integration testing with containerized deployment

## New MCP Functions Added

### **Enhanced Note Operations**
- **`update_note()`** - Now supports all REST API fields including note movement via `parent_id`
- **`bulk_move_notes(note_ids, target_notebook_id)`** - Move multiple notes to target notebook
- **`search_and_bulk_update_preview(query, preview_limit, inspect_count)`** - Preview bulk operations
- **`search_and_bulk_update_execute(query, expected_count, first_title, ...)`** - Execute bulk updates safely

### **Bulk Update Workflow**
1. **Preview**: `search_and_bulk_update_preview("project")` → See total count + sample notes + content
2. **Execute**: `search_and_bulk_update_execute("project", 47, "Project Meeting", parent_id="archive_id")` → Bulk move with safety verification

### **Tool Count Update**
The server now provides **25 tools** (up from 21):
- Added: `bulk_move_notes`, `search_and_bulk_update_preview`, `search_and_bulk_update_execute`
- Enhanced: `update_note` with full REST API support