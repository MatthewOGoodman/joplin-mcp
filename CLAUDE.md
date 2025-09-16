# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Background & Goals

This is a **fork of alondmnt's joplin-mcp** project, chosen for its comprehensive feature set and mature implementation. Our goals are to enhance it with:

### ✅ Completed Enhancements

1. **Enhanced Note Operations (COMPLETED)**:
   - ✅ Enhanced `update_note()` with full REST API support including `parent_id` field
   - ✅ Added `bulk_move_notes()` for moving multiple notes between notebooks
   - ✅ Added `search_and_bulk_update_preview()` for safe bulk operation previews
   - ✅ Added `search_and_bulk_update_execute()` for verified bulk updates
   - ✅ **New**: Added `bulk_tag_notes()` for applying multiple tags to multiple notes

2. **Docker Make Pipeline (COMPLETED)**:
   - ✅ Ported multi-stage Dockerfile with development and production targets
   - ✅ Created comprehensive Makefile with build, run, test, and cleanup targets  
   - ✅ Added docker-compose.yml for production multi-MCP deployments
   - ✅ Configured proper networking and environment variable handling
   - ✅ **Credits**: Docker Make pipeline implementation inspired by [JPFrancoia/jopmcp](https://github.com/JPFrancoia/jopmcp)

3. **Token and Configuration Management Strategy (COMPLETED)**:

**Strategy Overview**: Leverage alondmnt's original token management while enabling deployment mode switching
   
**Token Flow Architecture**:
- **`joplin-mcp.json`** (Server Config): Stores token, tools, connection settings via alondmnt's `JoplinMCPConfig.load()`
- **`claude_desktop_config.json`** (Launch Instructions): Contains deployment-specific server launch commands
- **Orthogonal Systems**: Token management and deployment switching are completely independent

**Implementation Plan**:
   - ✅ **Analysis Complete**: Understood alondmnt's 9-path auto-discovery system and token priority
   - ✅ **Template System**: Created `claude-desktop-config-complete.json.example` with 8 deployment modes
   - ✅ **Step 1 COMPLETE**: Fixed `joplin-mcp.json` token to use environment variable fallback
   - ✅ **Step 2 COMPLETE**: Verified existing `switch_mode.py` works correctly with new token strategy
   - ✅ **Step 3 COMPLETE**: Environment variable dependencies are intentional (alondmnt's backup mechanism)
   - ✅ **Step 4 COMPLETE**: Tested complete flow - all components working as intended

**Test Results Summary**:
   - ✅ **Token Discovery**: `joplin-mcp.json` with `token: null` correctly triggers `JOPLIN_TOKEN` env var fallback
   - ✅ **MCP Server Startup**: Docker container starts successfully with environment variable, fails appropriately when missing
   - ✅ **Claude Desktop Integration**: Current config properly passes environment variables to container
   - ✅ **Deployment Switching**: Existing `switch_mode.py` works with template system and token flow

**STRATEGY COMPLETE**: Successfully aligned our deployment switching with alondmnt's original token management

### Tool Count Update
The server now provides **27 tools** (up from 21):
- **Added**: `move_note` (single note moves), `bulk_move_notes` (batch moves), `bulk_tag_notes` (batch tagging), `strip_note_tags` (remove all tags from single note), `search_and_bulk_update_preview` (safe bulk previews), `search_and_bulk_update_execute` (verified bulk updates)  
- **Enhanced**: `update_note` with extended REST API fields and user-friendly `parent_notebook` parameter

### API Design Rationale

**Function Usage Guidelines**:

**For Content Updates:**
- `update_note()` - General-purpose updates including content, metadata, AND movement
- Use when combining content changes with moves: `update_note(note_id, title="Archive Item", parent_id="abc123def456")`

**For Move-Only Operations (Clearer Intent):**
- `move_note()` - Single note moves between notebooks (dedicated function)
- `bulk_move_notes()` - Batch note moves between notebooks (dedicated function)
- Use these when you're only moving notes without other changes

**For Tag Operations:**
- `tag_note()` - Single tagging operations
- `bulk_tag_notes()` - Batch tagging operations

**Safety-First Bulk Updates**: No generic `bulk_update_note()` function exists by design:
- All bulk updates must use `search_and_bulk_update_*()` with mandatory safety verification
- Prevents accidental bulk modifications without preview and confirmation steps

**Key Insight**: `parent_id` is the notebook **ID** (hash string like "abc123def456"), not the notebook name


### ✅ Multi-MCP Docker Configuration (COMPLETED)

**Implementation**: Multi-MCP deployment achieved via docker-compose.yml with port-based separation:
- **Primary MCP**: Port 8080 (joplin-mcp-enhanced)
- **Additional MCPs**: Port 8081+ (configurable via MCP_PORT environment variable)
- **Transport**: Supports both STDIO (single-MCP) and HTTP/SSE (multi-MCP) transports
- **Orchestration**: Production deployment via `docker-compose up -d`

### ✅ Function Parallelism Verification (COMPLETED)

**Status**: Both `search_and_bulk_update_preview` and `search_and_bulk_update_execute` functions now use:
- Identical parameter processing and validation
- Centralized `JOPLIN_NOTE_FIELDS` registry for consistent field handling
- Same search logic, filtering, and result processing
- Shared helper functions for common operations
- Minimal differences limited to preview vs execution actions only

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

## Docker + MCP + Claude Desktop: Critical Learnings

**⚠️  IMPORTANT: These are hard-learned lessons from debugging Docker MCP integration.**

### 1. STDIO Transport Requirements for Claude Desktop

**Problem**: Claude Desktop uses STDIO transport to communicate with MCP servers, but Docker containers don't handle stdin/stdout correctly by default.

**Solution**: Always include `-i` flag in Docker run commands for STDIO transport:
```bash
docker run --rm -i --network host -v "$(pwd)/src:/app/src" [image] [command]
```
Without `-i`, the container exits immediately when Claude Desktop tries to send JSON-RPC messages.

### 2. macOS Docker Networking - localhost vs host.docker.internal

**Problem**: On macOS, Docker containers cannot reach services on the host using `localhost` due to Docker Desktop's VM architecture.

**Solution**: Use `host.docker.internal` to reach host services from Docker containers:
```bash
# ❌ WRONG - Will fail on macOS
JOPLIN_URL=http://localhost:41184

# ✅ CORRECT - Works on macOS
JOPLIN_URL=http://host.docker.internal:41184
```

### TODO: Cross-Platform Implementation
**Cross-Platform Considerations**:
- **Linux**: `localhost` works fine, `host.docker.internal` may not exist
- **macOS/Windows**: Must use `host.docker.internal`
- **Solution**: Use environment variable and configure per platform, or detect platform in code

### 3. Container State Management During Development

**Problem**: Docker containers persist between Claude Desktop restarts and configuration changes, leading to outdated containers running with old environment variables.

**Critical Debug Steps**:
1. **Always check running containers** when MCP issues occur:
   ```bash
   docker ps --filter "ancestor=your-image"
   ```

2. **Stop old containers** before testing configuration changes:
   ```bash
   docker stop $(docker ps -q --filter "ancestor=your-image")
   ```

3. **Clear Claude Desktop cache** AND restart the application (both required)

4. **Verify new containers** are using updated config by checking logs

### 4. FastMCP STDIO Transport Issues

**Problem**: Appeared that FastMCP 2.11.3+ has initialization sequence bugs with STDIO transport that cause "initialization not complete" errors.

**Root Cause**: The issue was NOT FastMCP version but Docker networking and missing `-i` flag.

**Debugging Mistake**: Assumed FastMCP version regression instead of checking Docker configuration first.

### 5. stdout Pollution in STDIO Transport

**Problem**: Any non-JSON output to stdout breaks MCP STDIO transport. FastMCP correctly sends banners to stderr, but custom runner scripts may pollute stdout.

**Solution**: 
- Never add print() statements to stdout in MCP server code
- FastMCP banners go to stderr (correct behavior)
- All debugging output must go to stderr: `print("debug", file=sys.stderr)`

### 6. Common Debugging Sequence for Docker MCP Issues

When MCP server fails to connect:

1. **Test host connectivity first**:
   ```bash
   curl "http://localhost:41184/ping?token=YOUR_TOKEN"
   ```

2. **Test Docker container connectivity**:
   ```bash
   docker run --rm -i your-image python -c "import requests; print(requests.get('http://host.docker.internal:41184/ping?token=YOUR_TOKEN').text)"
   ```

3. **Check running containers** (often the real issue):
   ```bash
   docker ps | grep your-image
   ```

4. **Test STDIO manually**:
   ```bash
   echo '{"jsonrpc":"2.0","method":"initialize",...}' | docker run --rm -i your-image your-command
   ```

5. **Only then** investigate code-level issues

### 7. Volume Mount Validation

**Problem**: Volume mounts fail silently if source paths have spaces/special characters.

**Solution**: Always quote paths and test volume mounting:
```bash
# Test volume mount is working
docker run --rm -v "$(pwd)/src:/app/src" your-image ls -la /app/src
```

### Frequent Mistakes to Avoid

1. **Assuming FastMCP version issues** before checking Docker networking
2. **Not stopping old containers** when testing configuration changes  
3. **Forgetting `-i` flag** for STDIO transport
4. **Using localhost** instead of host.docker.internal on macOS
5. **Not verifying volume mounts** are working correctly
6. **Polluting stdout** in MCP server code
7. **Not checking docker ps** when containers seem to be failing
8. **Environment Variable Mismatch** - Setting wrong environment variables that don't match what the server code actually reads

### Critical Troubleshooting Issue: Tunnel Vision

**Problem**: Getting fixated on complex explanations (cache corruption, version conflicts, networking bugs) when the root cause is much simpler.

**Example Case**: Spent extensive time debugging "phantom MCP configuration caches" and FastMCP version issues when the actual problem was setting `JOPLIN_URL` environment variable instead of the `JOPLIN_HOST` and `JOPLIN_PORT` variables that the server code actually reads.

**Warning Signs of Tunnel Vision**:
- Pursuing increasingly complex theories without validating basic assumptions
- Ignoring user suggestions that point to simpler explanations
- Not checking what the actual code does vs. what you assume it does
- Focusing on external factors (caching, versions) before internal factors (configuration)

**Better Approach**:
1. **Start with the fundamentals** - What environment variables does the actual server code read?
2. **Listen to user insights** - They often spot patterns you miss
3. **Check running processes** - What containers are actually running with what configs?
4. **Read the source code** - Don't assume, verify what variables are actually used
5. **Test one variable at a time** - Isolate each potential cause

**Key Learning**: When debugging complex systems, the most sophisticated-looking problem often has the simplest cause. Always verify that your configuration matches what the code actually expects before exploring exotic failure modes.

### 8. MCP Function Architecture: No Cross-Function Calls

**Problem**: Attempting to call MCP tool functions from within other MCP tool functions leads to "'FunctionTool' object is not callable" errors.

**Root Cause**: MCP tool functions decorated with `@create_tool` become **FastMCP FunctionTool objects** at runtime, not regular Python functions. They are designed as **external API endpoints** for AI agents, not internal utilities.

**alondmnt's Correct Pattern** (never calls MCP functions from MCP functions):
```python
# ✅ CORRECT: Direct Joplin API calls within MCP functions
@create_tool("get_links", "Extract links from note")
async def get_links(note_id: str) -> str:
    client = get_joplin_client()
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)  # Direct API call
    # ... process note data
```

**Our Problematic Pattern** (tried to call MCP functions from MCP functions):
```python
# ❌ WRONG: Calling MCP tool functions from within MCP tool functions
@create_tool("search_and_bulk_update_preview", "Preview bulk update")
async def search_and_bulk_update_preview(query: str) -> str:
    preview_result = await find_notes(query, ...)  # FAILS: find_notes is FunctionTool, not function
    note_content = await get_note(note_id)         # FAILS: get_note is FunctionTool, not function
```

**Correct Fix Pattern** (follow alondmnt's direct API approach):
```python
# ✅ CORRECT: Use underlying Joplin API calls directly
@create_tool("search_and_bulk_update_preview", "Preview bulk update")
async def search_and_bulk_update_preview(query: str) -> str:
    client = get_joplin_client()
    results = client.search_all(query=query, fields=COMMON_NOTE_FIELDS)  # Direct API
    notes = process_search_results(results)                               # Helper functions OK
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)          # Direct API
```

**Key Insights**:
1. **MCP functions are endpoints, not utilities** - They're meant to be called by AI agents via MCP protocol, not by other Python functions
2. **Single-layer abstraction principle** - Each MCP tool should be a thin wrapper around direct API calls
3. **Helper functions are fine** - Non-decorated utility functions like `process_search_results()`, `build_search_filters()` can be called normally
4. **Listen to architectural intuition** - When users suggest direct API calls over function composition, they're often right about the intended architecture

**Warning Signs of This Anti-Pattern**:
- "'FunctionTool' object is not callable" errors
- Trying to await MCP tool functions from within other MCP tool functions
- Complex function call chains within MCP tools
- Ignoring user suggestions to use direct API calls

**Debugging Approach**:
1. Check if any `@create_tool` decorated functions are being called from within other `@create_tool` functions
2. Replace MCP function calls with direct `client.method()` calls to underlying APIs
3. Keep MCP functions as simple, single-purpose endpoints
4. Use non-decorated helper functions for code reuse instead of MCP function composition

### 9. MCP Cache Management: Three Levels of Claude Desktop Reset

**Problem**: After fixing code issues and rebuilding Docker containers, Claude Desktop may still use cached MCP server definitions, leading to stale function behavior or "function not found" errors.

**Claude Desktop Reset Hierarchy** (use appropriate level based on issue severity):

#### **Level 1: Simple Restart** (First attempt - least disruptive)
- **When to use**: Basic function updates, minor code changes
- **Steps**: 
  1. Quit Claude Desktop completely (Cmd+Q on macOS - never just minimize)
  2. Stop/rebuild Docker containers while Claude Desktop is closed
  3. Restart Claude Desktop
- **No data loss**: Preserves login, settings, conversation history

#### **Level 2: Clear Cache and Restart** (Moderate disruption)
- **When to use**: Level 1 failed, persistent stale cache, MCP connection issues
- **Steps**:
  1. In Claude Desktop: Help → Troubleshooting → Clear Cache and Restart
  2. **Additional step**: Quit Claude Desktop again after it restarts (Cmd+Q)
  3. Stop/remove Docker containers while Claude Desktop is fully closed:
     ```bash
     docker stop $(docker ps -q --filter "ancestor=joplin-mcp:dev-latest")
     docker rm $(docker ps -aq --filter "ancestor=joplin-mcp:dev-latest")
     ```
  4. Rebuild and restart containers
  5. Restart Claude Desktop
- **Requires re-login**: May need to authenticate again

#### **Level 3: Reset App Data** (Nuclear option - maximum disruption)
- **When to use**: Level 2 failed, persistent config corruption, MCP protocol issues
- **Steps**:
  1. **BACKUP CONFIG FIRST** - Save these Claude Desktop config files:
     ```bash
     # macOS paths (save these files before reset):
     ~/Library/Application\ Support/Claude/claude_desktop_config.json
     ~/Library/Application\ Support/Claude/claude_ui_config.json
     
     # Example backup commands:
     cp ~/Library/Application\ Support/Claude/claude_desktop_config.json ./claude_desktop_config_backup.json
     cp ~/Library/Application\ Support/Claude/claude_ui_config.json ./claude_ui_config_backup.json
     ```
  2. In Claude Desktop: Help → Troubleshooting → Reset App Data
  3. Quit Claude Desktop completely (Cmd+Q)
  4. Stop/remove all Docker containers and images:
     ```bash
     docker stop $(docker ps -q --filter "ancestor=joplin-mcp")
     docker rm $(docker ps -aq --filter "ancestor=joplin-mcp")
     docker rmi $(docker images -q joplin-mcp)
     ```
  5. Rebuild everything from scratch
  6. Restart Claude Desktop
  7. **RESTORE CONFIG** - Copy the backup files back:
     ```bash
     cp ./claude_desktop_config_backup.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
     cp ./claude_ui_config_backup.json ~/Library/Application\ Support/Claude/claude_ui_config.json
     ```
  8. Quit and restart Claude Desktop once more to load restored config
- **Complete reset**: Loses all settings, conversations, requires full reconfiguration

**Debug Workflow Decision Tree**:

1. **Start with Level 1** for routine code changes
2. **Escalate to Level 2** if you see:
   - Old error messages after container rebuild
   - Functions missing or showing old signatures
   - MCP connection failures
3. **Use Level 3** only if you see:
   - Persistent config corruption
   - MCP protocol errors after Level 2
   - Complete inability to connect to rebuilt containers

**Critical Timing**: Always stop/rebuild Docker containers **while Claude Desktop is fully closed** between steps 2-4 of each level.

**Common Mistakes**:
- ❌ Using Level 3 (Reset App Data) for simple code changes
- ❌ Not backing up config files before Level 3 reset
- ❌ Rebuilding containers while Claude Desktop is still running
- ❌ Assuming Level 1 restart is sufficient for deep cache issues
- ❌ Not quitting Claude Desktop after Level 2 "Clear Cache and Restart"
- ❌ Forgetting to restart Claude Desktop after restoring Level 3 config files

**Key Insight**: The three levels correspond to different cache depths in Claude Desktop's MCP client. Use the minimum necessary level to avoid unnecessary disruption.

**For This Specific Fix**: Use **Level 1** - we fixed a code error, rebuilt the container, so a simple Claude Desktop restart should be sufficient to pick up the corrected `search_and_bulk_update_preview` function.

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

## Enhancement Implementation Status

### ✅ Phase 1: Enhanced Note Movement (COMPLETED)
- **Enhanced `update_note()` function** - Added all REST API parameters including `parent_id`, GPS coordinates, timestamps, etc.
- **Implemented `bulk_move_notes()`** - Batch move multiple notes between notebooks with detailed error reporting
- **Added `search_and_bulk_update_preview()`** - Three-level preview system (count + metadata + content inspection)
- **Added `search_and_bulk_update_execute()`** - Safe bulk updates with verification and all update_note parameters

### ✅ Phase 2: Docker Integration (COMPLETED)
- **Ported multi-stage Dockerfile** - Development and production targets with hot-reload support
- **Created comprehensive Makefile** - Build, run, test, and cleanup targets optimized for development workflow
- **Added docker-compose.yml** - Production deployment with multi-MCP support
- **Configured network and transport** - Host networking for Joplin web clipper access, SSE transport support
- **Environment variable setup** - JOPLIN_TOKEN, MCP_PORT, transport configuration

### ✅ Phase 3: Additional Enhancements (COMPLETED)
- ✅ Enhanced error handling following alondmnt's patterns
- ✅ User-friendly notebook name parameters for all move operations  
- ✅ Bulk tagging operations with comprehensive error reporting
- ✅ Tag removal functionality (`strip_note_tags`)
- ✅ Integration testing with containerized deployment

## New MCP Functions Added

### **Enhanced Note Operations**
- **`update_note()`** - Enhanced with extended REST API fields and user-friendly `parent_notebook` parameter
- **`move_note(note_id, target_notebook="Archive")`** - Move single note between notebooks (supports notebook names)
- **`bulk_move_notes(note_ids, target_notebook="Archive")`** - Move multiple notes to target notebook (supports notebook names)
- **`bulk_tag_notes(note_ids, tag_names)`** - Apply multiple tags to multiple notes
- **`strip_note_tags(note_id)`** - Remove all tags from a single note
- **`search_and_bulk_update_preview(query, parent_notebook="Archive")`** - Preview bulk operations (supports notebook names)
- **`search_and_bulk_update_execute(query, expected_count, first_title, parent_notebook="Archive")`** - Execute bulk updates safely (supports notebook names)

### **Bulk Update Workflow**
1. **Preview**: `search_and_bulk_update_preview("project")` → See total count + sample notes + content
2. **Execute**: `search_and_bulk_update_execute("project", 47, "Project Meeting", parent_id="abc123def456")` → Bulk move with safety verification

### **Move Operation Examples**
- **Single move**: `move_note("note123", target_notebook="Archive")` → Move one note using notebook name
- **Batch move**: `bulk_move_notes(["note1", "note2", "note3"], target_notebook="Archive")` → Move multiple notes using notebook name  
- **Content + Move**: `update_note("note123", title="Archived Item", parent_notebook="Archive")` → Update and move using notebook name
- **Tag Cleanup**: `strip_note_tags("note123")` → Remove all tags from note

### **Tool Count Update**
The server now provides **27 tools** (up from 21):
- **Added**: `move_note` (single note moves), `bulk_move_notes` (batch moves), `bulk_tag_notes` (batch tagging), `strip_note_tags` (remove all tags from single note), `search_and_bulk_update_preview` (safe bulk previews), `search_and_bulk_update_execute` (verified bulk updates)
- **Enhanced**: `update_note` with extended REST API fields and user-friendly `parent_notebook` parameter

## Docker Development Workflow

### **Development Testing** (Hot-reload, volume mounting)
```bash
# Build development image
make build-dev

# Set Joplin token and run with volume mounting for live code changes
export JOPLIN_TOKEN="your_webclipper_token"
make dev

# View logs
make logs

# Stop container
make stop
```

### **Production Deployment** (Self-contained)
```bash
# Single container
export JOPLIN_TOKEN="your_webclipper_token"
make build-prod && make prod

# Multi-MCP orchestration (reads JOPLIN_TOKEN from .env file)
echo "JOPLIN_TOKEN=your_webclipper_token" > .env
docker-compose up -d
```

### **Requirements**
- **Joplin Desktop** running with Web Clipper enabled
- **JOPLIN_TOKEN** from Joplin Desktop → Tools → Options → Web Clipper → Authorization token
- **Network access** to localhost:41184 (Joplin web clipper port)