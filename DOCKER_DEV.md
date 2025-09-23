# Docker Development Guide for joplin-mcp

This guide documents Docker-based development workflows, critical debugging lessons, and configuration management for MCP (Model Context Protocol) server development.

## Overview

Docker development provides isolated, reproducible environments for MCP server development with features like hot-reload, cross-platform networking, and standardized debugging workflows. This implementation was developed specifically for joplin-mcp but contains patterns applicable to any MCP project.

## Quick Start

### Development Workflow (Hot-reload, volume mounting)
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

### Production Deployment (Self-contained)
```bash
# Single container
export JOPLIN_TOKEN="your_webclipper_token"
make build-prod && make prod

# Multi-MCP orchestration (reads JOPLIN_TOKEN from .env file)
echo "JOPLIN_TOKEN=your_webclipper_token" > .env
docker-compose up -d
```

### Requirements
- **Joplin Desktop** running with Web Clipper enabled
- **JOPLIN_TOKEN** from Joplin Desktop → Tools → Options → Web Clipper → Authorization token
- **Network access** to localhost:41184 (Joplin web clipper port)
- **Docker installed** for containerized deployments

## MCP Configuration Management System

### Available Deployment Modes
```bash
./mcp-config-manager.sh docker-dev      # Development with live code changes
./mcp-config-manager.sh docker-prod     # Production Docker deployment
./mcp-config-manager.sh python-uvx      # Quick deployment testing (zero-install)
./mcp-config-manager.sh python-installed # Installed Python package
```

### Management Commands
```bash
./mcp-config-manager.sh backup          # Backup current configurations
./mcp-config-manager.sh restore [file]  # Restore from backup (latest if no file)
./mcp-config-manager.sh status          # Show current status and server counts
```

### Entry Point Strategy
- **Development**: `docker-dev` → `run_fastmcp_server.py` (enhanced CLI options)
- **Package Testing**: `python-uvx` → `uvx joplin-mcp` (quick deployment validation)
- **Production**: `docker-prod`, `python-installed` → `joplin_mcp.server` (official entry points)

### Key Features
- **Smart Backup System**: Timestamped backups with validation (stored in `~/.mcp-config-backups/`)
- **Token Management**: Automatic JOPLIN_TOKEN extraction from backups or environment
- **Configuration Merging**: Preserves other MCP servers during switches
- **Claude Desktop Reset Recovery**: Full restoration after app resets
- **Server Count Validation**: Reports MCP server counts for current configs and backups
- **Cross-Platform**: Supports macOS, Linux, and Windows Claude Desktop paths

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

### Common Debugging Mistakes to Avoid

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

## Claude Desktop Cache Management: Three Levels of Reset

**Problem**: After fixing code issues and rebuilding Docker containers, Claude Desktop may still use cached MCP server definitions, leading to stale function behavior or "function not found" errors.

**Claude Desktop Reset Hierarchy** (use appropriate level based on issue severity):

### Level 1: Simple Restart (First attempt - least disruptive)
- **When to use**: Basic function updates, minor code changes
- **Steps**:
  1. Quit Claude Desktop completely (Cmd+Q on macOS - never just minimize)
  2. Stop/rebuild Docker containers while Claude Desktop is closed
  3. Restart Claude Desktop
- **No data loss**: Preserves login, settings, conversation history

### Level 2: Clear Cache and Restart (Moderate disruption)
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

### Level 3: Reset App Data (Nuclear option - maximum disruption)
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

### Debug Workflow Decision Tree

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

## Configuration Flow Architecture

### CRITICAL BUG: Docker Networking Configuration Flow

**Problem Identified**: The installation process creates inconsistent configurations where `joplin-mcp.json` has `"host": "localhost"` but Claude Desktop environment variables have `"JOPLIN_HOST": "host.docker.internal"`. The MCP server reads the JSON file first, ignoring environment variables, causing connection failures.

### Root Cause Analysis

**Current Broken Flow**:
1. `run_installation_process()` → `config_path_resolver(token)` → `create_joplin_config()`
2. `JoplinMCPConfig.create_interactively()` → Creates config with hardcoded `DEFAULT_CONNECTION["host"] = "localhost"`
3. `config.save_interactively()` → Saves joplin-mcp.json with localhost
4. `update_chat_interface_config()` → `create_base_mcp_config()` → Reads JSON file, creates env vars
5. **Broken addition**: `create_base_mcp_config()` applies Docker networking fix to environment variables only
6. **Result**: JSON file has localhost, environment variables have host.docker.internal, MCP server uses JSON file

**What Each File Contains**:

**joplin-mcp.json (Server Config)**:
- **Purpose**: Configuration file read by MCP server at startup
- **Contains**: `host`, `port`, `token`, `verify_ssl`, `timeout`, tool permissions, content privacy
- **Read by**: MCP server process when starting up

**claude_desktop_config.json (Launch Instructions)**:
- **Purpose**: Tells Claude Desktop how to launch the MCP server
- **Contains**: `command`, `args`, `env` (environment variables that override JSON settings)
- **Used by**: Claude Desktop to spawn MCP server process

### alondmnt's Original Flow (No Deployment Awareness)

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

### Fixed Strategy - Minimal Modifications to alondmnt's Flow

**Solution Overview**: Add deployment/OS awareness to config creation, use template-based configuration from `claude-desktop-config-complete.json.example`, ensure JSON file and environment variables are consistent.

**Modified Function Flow**:

**Step 1: Add User Choices to `run_installation_process()`**
```python
def run_installation_process(...):
    # Step 1: Get Joplin API token
    token = get_token_interactively()

    # Step 2: NEW - Get deployment choices
    deployment_type = get_deployment_choice()  # "python" or "docker"
    is_development = get_mode_choice()         # True/False

    # Step 3: Create/update Joplin configuration with deployment info
    config_path = config_path_resolver(token, deployment_type, is_development)
```

**Step 2: Enhance `create_joplin_config()` to Accept Deployment Info**
```python
def create_joplin_config(token: str, deployment_type: str, is_development: bool) -> Path:
    # Pass deployment info to config creation
    config = JoplinMCPConfig.create_interactively(
        token=token,
        deployment_type=deployment_type,
        is_development=is_development,
        include_permissions=True
    )
```

**Step 3: Modify `JoplinMCPConfig.create_interactively()` to Use Templates**
```python
@classmethod
def create_interactively(cls, token=None, deployment_type="python", is_development=False, ...):
    # Read from claude-desktop-config-complete.json.example instead of DEFAULT_CONNECTION
    template_config = read_deployment_template(deployment_type, is_development)

    # Apply OS-specific networking fixes
    final_config = apply_os_networking_fix(template_config, deployment_type)

    # Create config object with correct host values
    config_kwargs = {
        "host": final_config["host"],  # Already correct for deployment + OS
        "port": final_config["port"],
        "token": token,
        # ... other settings
    }
    return cls(**config_kwargs)
```

**Step 4: Helper Functions for Template Reading**
```python
def read_deployment_template(deployment_type: str, is_development: bool) -> Dict:
    """Read the appropriate config template from claude-desktop-config-complete.json.example"""
    # Map deployment choices to template keys:
    # python + production → "joplin-python-installed"
    # python + development → "joplin-python-installed" (same)
    # docker + development → "joplin-docker-dev"
    # docker + production → "joplin-docker-prod"

def apply_os_networking_fix(config: Dict, deployment_type: str) -> Dict:
    """Apply OS-specific networking fixes for Docker deployments"""
    import platform
    if deployment_type == "docker" and platform.system() in ["Darwin", "Windows"]:
        # Convert localhost to host.docker.internal for Docker on macOS/Windows
        # Extract host from env vars or default locations
        config["host"] = "host.docker.internal"
    return config
```

**Step 5: Simplify `create_base_mcp_config()`**
```python
def create_base_mcp_config(self, config_path, is_development, deployment_type):
    # Remove all Docker networking logic - now handled during config creation
    # Just read the final config and create environment variables
    env_vars = self.get_joplin_environment_variables(config_path)
    # Environment variables now match JSON file - no more fixes needed
    return mcp_config
```

### Deployment Template System

**Template File**: `claude-desktop-config.deployment-templates.json`

This file contains configuration patterns for 8 deployment modes (4 current + 4 future):

**Current Deployable Modes (4)** - STDIO Transport:
- **Python + Production**: `"joplin-python-installed"` → Uses `"command": "joplin-mcp-server"` (stable pip package)
- **Python + Development**: `"joplin-python-uvx"` → Uses `"command": "uvx", "args": ["joplin-mcp"]` (quick package testing)
- **Docker + Development**: `"joplin-docker-dev"` → Volume mounts source code for live changes
- **Docker + Production**: `"joplin-docker-prod"` → Self-contained image with packaged code

**Future HTTP Transport Modes (4)** - Multi-MCP Support:
- **SSE Transport**: `"joplin-sse"` → Server-Sent Events (requires separate server startup)
- **HTTP Transport**: `"joplin-http"` → Standard HTTP (requires separate server startup)
- **Streamable HTTP**: `"joplin-streamable-http"` → Streaming HTTP (requires separate server startup)
- **Docker SSE**: `"joplin-docker-sse"` → Containerized SSE transport

**Key Design Principles**:
1. **Template-driven configuration**: Code reads templates and fills in project-specific paths
2. **Minimal environment variables**: Templates use only `"JOPLIN_TOKEN": "${JOPLIN_TOKEN}"`
3. **Transport separation**: STDIO for current single MCP, HTTP for future multi-MCP deployments
4. **OS-aware networking**: Applied only when necessary (Docker on macOS/Windows)
5. **Development philosophy**:
   - Python development uses `uvx` for quick package testing (validates packaging works)
   - Real development work uses Docker with live code mounting

### Benefits of This Approach
1. **Minimal changes** to alondmnt's proven flow
2. **Template-based configuration** eliminates hardcoded defaults
3. **Consistent JSON and environment variables** - no more disconnects
4. **OS-aware networking** applied during config creation, not as an afterthought
5. **`create_base_mcp_config()` becomes simple** - no more orphaned logic

### Implementation Order
1. Create template reading functions
2. Modify `JoplinMCPConfig.create_interactively()` to use templates
3. Add deployment choice functions to `run_installation_process()`
4. Update `create_joplin_config()` signature and calls
5. Simplify `create_base_mcp_config()` by removing Docker networking logic
6. Test end-to-end flow

## Command-Line Installation Strategy

### Parallel Implementation for Command-Line Arguments

**Current alondmnt Flow:**
1. `install.py` → `run_installation_process()` → `get_token_interactively()` → `create_joplin_config()` → `JoplinMCPConfig.create_interactively()`
2. **Always interactive** - prompts for token, deployment choices, tool permissions

**Proper Solution: Add Parallel Non-Interactive Path**

### Step 1: Command Line Argument Detection
```python
def main():
    args = parse_args()

    if has_command_args(args):
        # NEW: Direct command-line flow
        return run_command_line_installation(args)
    else:
        # EXISTING: alondmnt's interactive flow (unchanged)
        return run_installation_process(
            config_path_resolver=create_joplin_config,
            is_development=True,
            welcome_message="Welcome! This script will help you set up the Joplin MCP server."
        )
```

### Step 2: Parallel Non-Interactive Implementation
```python
def run_command_line_installation(args):
    """Parallel implementation that bypasses alondmnt's interactive flow entirely."""

    # Token: CLI arg > env var > error
    token = args.token or os.environ.get("JOPLIN_TOKEN")
    if not token:
        print_error("Token required. Use --token TOKEN or set JOPLIN_TOKEN env var")
        return 1

    # Deployment type from args
    deployment_type = args.deployment

    # Create config using direct JoplinMCPConfig constructor (NOT create_interactively)
    config = create_command_line_config(token, deployment_type)

    # Save config directly
    config_path = save_config(config)

    # Update Claude Desktop config directly
    update_claude_desktop_config(config_path, deployment_type)

    # Handle Docker builds if needed
    if deployment_type == "docker":
        build_docker_images()
```

### Step 3: Non-Interactive Config Creation
```python
def create_command_line_config(token: str, deployment_type: str) -> JoplinMCPConfig:
    """Create config with safe defaults, bypassing all interactive prompts."""

    # Get alondmnt's safe defaults for tools
    safe_tools = JoplinMCPConfig.get_safe_defaults()  # This should exist

    # OS-aware host selection
    import platform
    host = "localhost"
    if deployment_type == "docker" and platform.system() in ["Darwin", "Windows"]:
        host = "host.docker.internal"

    # Create config directly (no interactivity)
    return JoplinMCPConfig(
        host=host,
        port=41184,
        token=token,
        timeout=30,
        verify_ssl=False,
        tools=safe_tools,  # Use alondmnt's defaults
        content_exposure=JoplinMCPConfig.get_default_content_exposure()
    )
```

### Step 4: Command Line Args
```python
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command-args", action="store_true", help="Use command-line mode (non-interactive)")
    parser.add_argument("--token", help="Joplin API token")
    parser.add_argument("--deployment", choices=["python", "docker"], help="Deployment type")
    return parser.parse_args()

def has_command_args(args):
    """Check if any command-line args were provided."""
    return args.command_args or args.token or args.deployment
```

### Key Benefits of This Approach
1. **Zero modification** to alondmnt's existing flow
2. **Parallel implementation** that handles command-args separately
3. **Reuses alondmnt's safe defaults** for tool permissions
4. **Clean separation** between interactive and non-interactive modes
5. **Direct config creation** without hacking create_interactively()

## Future: MCP Docker Development Toolkit Extraction

This Docker development approach has been designed with extraction in mind. The goal is to create a standalone `mcp-docker-dev` package that can be used with ANY MCP project, not just joplin-mcp.

### Planned Toolkit Architecture
```
any-mcp-project/
├── src/your_mcp/
├── pyproject.toml
└── mcp-dev-toolkit/           # Drop-in development package
    ├── Dockerfile.template    # ${PROJECT_NAME}, ${PACKAGE_NAME} substitution
    ├── Makefile               # Standardized MCP dev commands
    ├── docker-compose.yml.template
    ├── claude-desktop-config.template.json
    └── scripts/
        ├── install-dev-tools.py
        ├── switch-mode.py     # Mode switching for any MCP project
        └── detect-project.py  # Auto-parse project metadata
```

### Key Features for Extraction
- **Template-driven Docker setup** with `${PROJECT_NAME}`, `${PACKAGE_NAME}` substitution
- **Project auto-detection** (parse `pyproject.toml` for package name/entry points)
- **Cross-platform networking fixes** (host.docker.internal/localhost detection)
- **Hot-reload development environment** with volume mounting
- **Port auto-assignment** for multi-MCP development
- **Claude Desktop config template generation**

### Benefits of Extraction
- **Community Value**: Reusable across all MCP projects, not tied to Joplin
- **No Upstream Conflicts**: Completely separate from alondmnt's codebase
- **Focused Contributions**: Clean joplin-mcp PR without Docker complexity
- **Personal Utility**: Standardized development workflow across your MCP projects
- **Potential Impact**: Could become standard MCP development toolkit

This documentation preserves all the hard-learned Docker development knowledge while preparing for its extraction into a more widely useful toolkit.