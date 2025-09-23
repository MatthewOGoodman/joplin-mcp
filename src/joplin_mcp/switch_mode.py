#!/usr/bin/env python3
"""Mode switching for MCP deployments.

This script allows switching between development and production modes
within your chosen deployment type (Python or Docker).

Designed to be generalizable for any MCP project.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from .ui_integration import (
    print_step, print_success, print_error, print_warning, print_info, print_colored, Colors,
    ClaudeDesktopInterface
)
from .config import JoplinMCPConfig


class MCPModeConfig:
    """Configuration for MCP mode switching - designed to be generalizable."""
    
    def __init__(
        self, 
        mcp_server_name: str = "joplin",
        docker_dev_image: str = "joplin-mcp:dev",
        docker_prod_image: str = "joplin-mcp:prod", 
        python_dev_script: str = "run_fastmcp_server.py",
        python_prod_command: str = "joplin-mcp-server",
        config_paths: list = None
    ):
        """Initialize MCP mode switching configuration.
        
        Args:
            mcp_server_name: Name of MCP server in Claude Desktop config
            docker_dev_image: Docker image name for development mode
            docker_prod_image: Docker image name for production mode
            python_dev_script: Python script name for development mode
            python_prod_command: Command for Python production mode
            config_paths: List of paths to search for MCP config files
        """
        self.mcp_server_name = mcp_server_name
        self.docker_dev_image = docker_dev_image
        self.docker_prod_image = docker_prod_image
        self.python_dev_script = python_dev_script
        self.python_prod_command = python_prod_command
        self.config_paths = config_paths or JoplinMCPConfig.get_default_config_paths()


def detect_current_deployment(mcp_config: MCPModeConfig) -> tuple[str, bool]:
    """Detect current deployment type and mode from Claude Desktop config.
    
    Args:
        mcp_config: MCP-specific configuration
        
    Returns:
        Tuple of (deployment_type, is_development)
    """
    try:
        claude_interface = ClaudeDesktopInterface()
        claude_config_path = claude_interface.find_config_file()
        
        if not claude_config_path or not claude_config_path.exists():
            print_error("Claude Desktop config not found. Please run installation first.")
            sys.exit(1)
        
        with open(claude_config_path) as f:
            claude_config = json.load(f)
        
        if "mcpServers" not in claude_config or mcp_config.mcp_server_name not in claude_config["mcpServers"]:
            print_error(f"{mcp_config.mcp_server_name} MCP not found in Claude Desktop config. Please run installation first.")
            sys.exit(1)
        
        server_config = claude_config["mcpServers"][mcp_config.mcp_server_name]
        command = server_config.get("command", "")
        args = server_config.get("args", [])
        
        # Detect deployment type and mode
        if command == "docker":
            deployment_type = "docker"
            # Check if using dev or prod image
            if mcp_config.docker_dev_image in args:
                is_development = True
            elif mcp_config.docker_prod_image in args:
                is_development = False
            else:
                print_error("Cannot determine Docker mode from config")
                sys.exit(1)
        elif command == mcp_config.python_prod_command:
            deployment_type = "python"
            is_development = False  # Production mode
        elif mcp_config.python_dev_script in str(args):
            deployment_type = "python" 
            is_development = True   # Development mode
        else:
            print_error("Cannot determine deployment type from Claude Desktop config")
            print_error(f"Found command: {command}, args: {args}")
            sys.exit(1)
        
        return deployment_type, is_development
        
    except Exception as e:
        print_error(f"Error reading Claude Desktop config: {e}")
        sys.exit(1)


def confirm_prod_switch() -> bool:
    """Confirm switching to prod mode (using installation-time code snapshot)."""
    print_warning("Switching to prod will use the code snapshot from previous installation.")
    print_warning("(Your current dev code in project directory will be preserved)")
    print_info("If you want to use your current code as the new prod version:")
    print_info("  Run the installation script again")
    print()
    
    while True:
        confirm = input(f"{Colors.CYAN}Continue with switch to previous prod version? (y/n): {Colors.END}").strip().lower()
        if confirm == 'y':
            return True
        elif confirm == 'n':
            print_error("Mode switch cancelled. Run installation script to reinstall with current code.")
            return False
        else:
            print_error("Please enter 'y' or 'n'")


def update_claude_config(
    mcp_config: MCPModeConfig,
    config_path: Path,
    deployment_type: str,
    is_development: bool
) -> bool:
    """Update Claude Desktop config with new mode settings.
    
    Args:
        mcp_config: MCP-specific configuration
        config_path: Path to MCP config file
        deployment_type: "python" or "docker"
        is_development: True for dev mode, False for prod mode
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use the existing interface update logic
        from .ui_integration import update_chat_interface_config
        
        return update_chat_interface_config(
            interface_name="claude",
            config_path=config_path,
            is_development=is_development,
            deployment_type=deployment_type
        )
        
    except Exception as e:
        print_error(f"Error updating Claude Desktop configuration: {e}")
        return False


def switch_mode(
    target_deployment: str = None,
    target_mode: str = None,
    mcp_config: MCPModeConfig = None
):
    """Switch between development and production modes.

    Args:
        target_deployment: Target deployment type ("python" or "docker"), defaults to current
        target_mode: Target mode ("dev" or "prod"), prompts if not specified
        mcp_config: MCP-specific configuration (defaults to Joplin MCP)
    """
    if mcp_config is None:
        mcp_config = MCPModeConfig()  # Default to Joplin MCP

    # Detect current state
    current_deployment, current_is_dev = detect_current_deployment(mcp_config)
    current_mode = "dev" if current_is_dev else "prod"

    print_step("Current Deployment Status")
    print_success(f"MCP Server: {mcp_config.mcp_server_name}")
    print_success(f"Deployment: {current_deployment}")
    print_success(f"Mode: {current_mode}")

    # Default to current deployment if not specified
    if not target_deployment:
        target_deployment = current_deployment
        print_colored(f"Using current deployment: {current_deployment}", Colors.WHITE)

    # Track if we're in interactive mode (target_mode not specified)
    interactive_mode = target_mode is None

    # Get target mode if not specified
    if not target_mode:
        print_colored(f"\nCurrent mode: {current_mode}", Colors.WHITE)
        print_colored("  1. Development (live code changes)", Colors.WHITE)
        print_colored("  2. Production (installation-time snapshot)", Colors.WHITE)

        choice = input(f"\n{Colors.CYAN}Enter choice (1 or 2): {Colors.END}").strip()
        if choice == "1":
            target_mode = "dev"
        elif choice == "2":
            target_mode = "prod"
        else:
            print_error("Invalid choice")
            sys.exit(1)

    target_is_dev = target_mode == "dev"

    # Check if already in target mode
    if current_deployment == target_deployment and current_is_dev == target_is_dev:
        print_success(f"Already in {target_deployment} {target_mode} mode!")
        return

    # Confirm switch to prod if needed (only in interactive mode)
    if current_is_dev and not target_is_dev and interactive_mode:  # dev → prod in interactive mode
        if not confirm_prod_switch():
            sys.exit(1)

    # Find MCP config file
    mcp_config_path = None
    for path in mcp_config.config_paths:
        if path.exists():
            mcp_config_path = path
            break

    if not mcp_config_path:
        print_error("MCP config file not found. Please run installation first.")
        sys.exit(1)

    # Update Claude Desktop config
    print_step(f"Switching to {target_deployment} {target_mode} mode")

    success = update_claude_config(
        mcp_config=mcp_config,
        config_path=mcp_config_path,
        deployment_type=target_deployment,
        is_development=target_is_dev
    )

    if success:
        print_success(f"Switched to {target_deployment} {target_mode} mode!")
        print_info("Please restart Claude Desktop to apply changes.")
    else:
        print_error("Failed to update Claude Desktop configuration")
        sys.exit(1)


def main():
    """Main entry point for mode switching script."""
    parser = argparse.ArgumentParser(
        description="Switch between MCP development and production modes"
    )
    parser.add_argument(
        "--mode",
        choices=["dev", "prod"],
        help="Target mode (dev or prod). If not specified, will prompt interactively."
    )
    parser.add_argument(
        "--deployment",
        choices=["python", "docker"],
        help="Target deployment type. If not specified, keeps current deployment."
    )
    # Generalization parameters
    parser.add_argument(
        "--mcp-name",
        default="joplin",
        help="Name of MCP server in Claude Desktop config (default: joplin)"
    )
    parser.add_argument(
        "--docker-dev-image",
        default="joplin-mcp:dev",
        help="Docker image name for development mode"
    )
    parser.add_argument(
        "--docker-prod-image", 
        default="joplin-mcp:prod",
        help="Docker image name for production mode"
    )
    parser.add_argument(
        "--python-dev-script",
        default="run_fastmcp_server.py",
        help="Python script name for development mode"
    )
    parser.add_argument(
        "--python-prod-command",
        default="joplin-mcp-server",
        help="Command for Python production mode"
    )
    
    args = parser.parse_args()
    
    print_colored("🔄 MCP Mode Switcher", Colors.BLUE + Colors.BOLD)
    print_colored("Switch between development and production modes", Colors.WHITE)
    
    # Create MCP configuration
    mcp_config = MCPModeConfig(
        mcp_server_name=args.mcp_name,
        docker_dev_image=args.docker_dev_image,
        docker_prod_image=args.docker_prod_image,
        python_dev_script=args.python_dev_script,
        python_prod_command=args.python_prod_command
    )
    
    try:
        switch_mode(
            target_deployment=args.deployment, 
            target_mode=args.mode,
            mcp_config=mcp_config
        )
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()