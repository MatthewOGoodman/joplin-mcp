#!/usr/bin/env python3
"""Installation script for Joplin MCP Server.

This script helps users set up the Joplin MCP server by:
1. Prompting for their Joplin API token
2. Creating/updating the joplin-mcp.json configuration file
3. Finding and updating the Claude Desktop configuration file
4. Building Docker image if --docker flag is used
5. Providing helpful instructions
"""

import json
import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Import UI functions from centralized module
from src.joplin_mcp.ui_integration import run_installation_process, print_step, print_success, print_error, print_colored, Colors

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent

def get_deployment_choice(cli_deployment: Optional[str] = None) -> str:
    """Ask user to choose between Python package and Docker deployment, or use CLI arg."""
    if cli_deployment:
        if cli_deployment.lower() in ["python", "docker"]:
            print_success(f"Using CLI deployment option: {cli_deployment}")
            return cli_deployment.lower()
        else:
            print_error(f"Invalid deployment option: {cli_deployment}. Must be 'python' or 'docker'")
            sys.exit(1)

    print_colored("\n🔧 Deployment Options", Colors.BLUE + Colors.BOLD)
    print_colored("Choose how you'd like to deploy Joplin MCP:", Colors.WHITE)
    print_colored("  1. Python Package (recommended for most users)", Colors.WHITE)
    print_colored("  2. Docker (for containerized environments)", Colors.WHITE)

    while True:
        choice = input(f"\n{Colors.CYAN}Enter your choice (1 or 2): {Colors.END}").strip()

        if choice == "1":
            print_success("Selected: Python Package deployment")
            return "python"
        elif choice == "2":
            print_success("Selected: Docker deployment")
            return "docker"
        else:
            print_error("Please enter 1 or 2")
            continue

def create_joplin_config(token: str) -> Path:
    """Create or update the joplin-mcp.json configuration file."""
    print_step("Creating Joplin MCP Configuration")

    project_root = get_project_root()
    config_path = project_root / "joplin-mcp.json"

    # Use centralized interactive config creation
    from src.joplin_mcp.config import JoplinMCPConfig

    config = JoplinMCPConfig.create_interactively(
        token=token,
        include_permissions=True,
        **JoplinMCPConfig.DEFAULT_CONNECTION
    )

    # Save configuration
    saved_path = config.save_interactively(config_path, include_token=True)

    print_success(f"Configuration saved to {saved_path}")
    return saved_path

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Install and configure Joplin MCP Server"
    )

    parser.add_argument(
        "--command-args",
        action="store_true",
        help="Use command-line mode (non-interactive)"
    )

    parser.add_argument(
        "--token",
        help="Joplin API token"
    )

    parser.add_argument(
        "--deployment",
        choices=["python", "docker"],
        help="Deployment type"
    )

    parser.add_argument(
        "--mode",
        choices=["development", "production"],
        default="development",
        help="Development or production mode (default: development)"
    )

    return parser.parse_args()

def has_command_args(args):
    """Check if any command-line args were provided."""
    return args.command_args or args.token or args.deployment

def create_command_line_config(token: str, deployment_type: str):
    """Create config with safe defaults, bypassing all interactive prompts."""
    from src.joplin_mcp.config import JoplinMCPConfig

    # OS-aware host selection
    import platform
    host = "localhost"
    if deployment_type == "docker" and platform.system() in ["Darwin", "Windows"]:
        host = "host.docker.internal"

    # Create config directly - alondmnt's constructor handles copying defaults
    return JoplinMCPConfig(
        host=host,
        port=41184,
        token=token,
        timeout=30,
        verify_ssl=False
        # tools and content_exposure will use DEFAULT_TOOLS.copy() and DEFAULT_CONTENT_EXPOSURE.copy()
    )

def run_command_line_installation(args):
    """Parallel implementation that bypasses alondmnt's interactive flow entirely."""

    # Token: CLI arg > env var > error
    token = args.token or os.environ.get("JOPLIN_TOKEN")
    if not token:
        print_error("Token required. Use --token TOKEN or set JOPLIN_TOKEN env var")
        return 1

    # Deployment type from args (required for command-line mode)
    deployment_type = args.deployment
    if not deployment_type:
        print_error("Deployment type required for command-line mode. Use --deployment {python,docker}")
        return 1

    # Mode from args (defaults to development)
    is_development = (args.mode == "development")

    print_colored(f"🚀 Non-interactive installation: {deployment_type} {args.mode}", Colors.BLUE + Colors.BOLD)

    # Prepare deployment infrastructure
    if deployment_type == "docker":
        from docker_build import validate_docker_environment, build_docker_images, cleanup_old_containers

        if not validate_docker_environment():
            print_error("Docker environment validation failed")
            return 1

        project_root = get_project_root()
        cleanup_old_containers(image_name="joplin-mcp")

        success = build_docker_images(
            project_root=project_root,
            image_name="joplin-mcp",
            build_dev=True,
            build_prod=True
        )

        if not success:
            print_error("Docker build failed")
            return 1

        print_success("Docker deployment ready!")

    # Create config using direct JoplinMCPConfig constructor (NOT create_interactively)
    config = create_command_line_config(token, deployment_type)

    # Save config using alondmnt's save_interactively (includes token)
    project_root = get_project_root()
    config_path = project_root / "joplin-mcp.json"
    config.save_interactively(config_path)
    print_success(f"Configuration saved to {config_path}")

    # Update Claude Desktop config using existing function
    from src.joplin_mcp.ui_integration import update_chat_interface_config
    update_chat_interface_config("claude", config_path, is_development=is_development, deployment_type=deployment_type)

    print_success(f"✅ {deployment_type.capitalize()} deployment installed successfully!")
    return 0


def main():
    """Main installation function with parallel command-line support."""
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

if __name__ == "__main__":
    sys.exit(main()) 