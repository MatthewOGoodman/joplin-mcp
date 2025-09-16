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
from pathlib import Path
from typing import Optional, Dict, Any

# Import UI functions from centralized module
from src.joplin_mcp.ui_integration import run_installation_process, print_step, print_success, print_error, print_colored, Colors

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent

def get_deployment_choice() -> str:
    """Ask user to choose between Python package and Docker deployment."""
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

def main():
    """Main installation function for development install."""
    return run_installation_process(
        config_path_resolver=create_joplin_config,
        is_development=True,
        welcome_message="Welcome! This script will help you set up the Joplin MCP server."
    )

if __name__ == "__main__":
    sys.exit(main()) 