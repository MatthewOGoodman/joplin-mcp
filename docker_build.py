#!/usr/bin/env python3
"""Docker build utilities for MCP projects.

This script provides Docker image building functionality that can be
reused across different MCP projects.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Import UI functions for consistent output
try:
    from src.joplin_mcp.ui_integration import (
        print_step, print_success, print_error, print_colored, Colors
    )
except ImportError:
    # Fallback for standalone usage
    def print_step(msg): print(f"🔧 {msg}")
    def print_success(msg): print(f"✅ {msg}")
    def print_error(msg): print(f"❌ {msg}")
    def print_colored(msg, color): print(msg)
    class Colors:
        BLUE = BOLD = END = ""


def validate_docker_environment() -> bool:
    """Validate Docker is available and running.
    
    Returns:
        True if Docker is ready, False otherwise
    """
    print_step("Validating Docker Environment")
    
    try:
        # Check if docker command exists
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        print_success("Docker command found")
        
        # Check if Docker daemon is running
        subprocess.run(["docker", "ps"], check=True, capture_output=True)
        print_success("Docker daemon is running")
        
        return True
        
    except FileNotFoundError:
        print_error("Docker not found. Please install Docker Desktop:")
        print_colored("  • Visit: https://www.docker.com/products/docker-desktop/", "")
        return False
        
    except subprocess.CalledProcessError:
        print_error("Docker daemon not running. Please start Docker Desktop:")
        print_colored("  • Start Docker Desktop application", "")
        print_colored("  • Wait for it to fully start", "")
        return False


def cleanup_old_containers(image_name: str = "joplin-mcp") -> None:
    """Clean up old Docker containers before building new images.
    
    Stops and removes containers with standard naming patterns and any containers
    built from the specified image to prevent conflicts with new deployments.
    
    Args:
        image_name: Base name of Docker images to clean up containers for
    """
    print_step("Cleaning up old containers")
    try:
        # Stop old containers (ignore errors if none exist)
        subprocess.run([
            "docker", "stop", f"{image_name}-dev", f"{image_name}-prod"
        ], capture_output=True, check=False)
        
        # Remove old containers (ignore errors if none exist)
        subprocess.run([
            "docker", "rm", f"{image_name}-dev", f"{image_name}-prod"
        ], capture_output=True, check=False)
        
        # Also clean up any containers from old image tags
        result = subprocess.run([
            "docker", "ps", "-aq", "--filter", f"ancestor={image_name}"
        ], capture_output=True, text=True, check=False)
        
        if result.stdout.strip():
            container_ids = result.stdout.strip().split('\n')
            subprocess.run([
                "docker", "stop"
            ] + container_ids, capture_output=True, check=False)
            subprocess.run([
                "docker", "rm"
            ] + container_ids, capture_output=True, check=False)
        
        print_success("Old containers cleaned up")
        
    except Exception as e:
        print_colored(f"Container cleanup had issues (this is usually fine): {e}", Colors.BLUE)


def build_docker_images(
    project_root: Path,
    image_name: str = "joplin-mcp",
    build_dev: bool = True,
    build_prod: bool = True,
    dockerfile_path: Optional[Path] = None
) -> bool:
    """Build Docker images for MCP deployment.
    
    Args:
        project_root: Path to project root directory
        image_name: Base name for Docker images
        build_dev: Whether to build development image
        build_prod: Whether to build production image
        dockerfile_path: Custom Dockerfile path (defaults to project_root/Dockerfile)
        
    Returns:
        True if all requested builds succeeded, False otherwise
    """
    print_step("Building Docker Images")
    
    # Validate Dockerfile exists
    if dockerfile_path is None:
        dockerfile_path = project_root / "Dockerfile"
    
    if not dockerfile_path.exists():
        print_error(f"Dockerfile not found at {dockerfile_path}")
        print_colored("Make sure the Dockerfile exists in the project directory", "")
        return False
    
    success = True
    
    try:
        if build_dev:
            # Build development image (with volume mounting support)
            print(f"Building development Docker image: {image_name}:dev")
            subprocess.run([
                "docker", "build", "--target", "development",
                "-t", f"{image_name}:dev", "."
            ], cwd=project_root, check=True)
            print_success(f"Development image built: {image_name}:dev")
        
        if build_prod:
            # Build production image (self-contained)
            print(f"Building production Docker image: {image_name}:prod")
            subprocess.run([
                "docker", "build", "--target", "production",
                "-t", f"{image_name}:prod", "."
            ], cwd=project_root, check=True)
            print_success(f"Production image built: {image_name}:prod")
        
        if build_dev and build_prod:
            print_success("All Docker images built successfully!")
        elif build_dev:
            print_success("Development Docker image built!")
        elif build_prod:
            print_success("Production Docker image built!")
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to build Docker image: {e}")
        print_colored("Please check the Dockerfile and try again", "")
        success = False
    
    return success


def list_docker_images(image_name: str = "joplin-mcp") -> List[str]:
    """List available Docker images for the MCP project.
    
    Args:
        image_name: Base name to search for
        
    Returns:
        List of image tags found
    """
    try:
        result = subprocess.run([
            "docker", "images", "--format", "{{.Repository}}:{{.Tag}}", 
            "--filter", f"reference={image_name}*"
        ], capture_output=True, text=True, check=True)
        
        images = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        return images
        
    except subprocess.CalledProcessError:
        return []


def clean_docker_images(image_name: str = "joplin-mcp", confirm: bool = True) -> bool:
    """Clean up Docker images for the MCP project.
    
    Args:
        image_name: Base name to clean up
        confirm: Whether to ask for confirmation
        
    Returns:
        True if cleanup succeeded, False otherwise
    """
    images = list_docker_images(image_name)
    
    if not images:
        print_success(f"No Docker images found for {image_name}")
        return True
    
    print_step(f"Found Docker images for {image_name}")
    for image in images:
        print_colored(f"  • {image}", "")
    
    if confirm:
        response = input(f"\nRemove all {len(images)} images? (y/n): ").strip().lower()
        if response != 'y':
            print_colored("Cleanup cancelled", "")
            return True
    
    try:
        for image in images:
            print(f"Removing {image}...")
            subprocess.run(["docker", "rmi", image], check=True, capture_output=True)
            print_success(f"Removed {image}")
        
        print_success("Docker cleanup completed!")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to remove Docker images: {e}")
        return False


def main():
    """Main entry point for Docker build script."""
    parser = argparse.ArgumentParser(
        description="Build Docker images for MCP projects"
    )
    parser.add_argument(
        "command",
        choices=["build", "list", "clean"],
        help="Command to execute"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Path to project root directory (default: current directory)"
    )
    parser.add_argument(
        "--image-name",
        default="joplin-mcp",
        help="Base name for Docker images (default: joplin-mcp)"
    )
    parser.add_argument(
        "--dev-only",
        action="store_true",
        help="Build only development image"
    )
    parser.add_argument(
        "--prod-only", 
        action="store_true",
        help="Build only production image"
    )
    parser.add_argument(
        "--dockerfile",
        type=Path,
        help="Custom Dockerfile path"
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompts"
    )
    
    args = parser.parse_args()
    
    print_colored("🐳 MCP Docker Build Utility", Colors.BLUE + Colors.BOLD)
    
    # Validate Docker environment for build/clean commands
    if args.command in ["build", "clean"]:
        if not validate_docker_environment():
            print_error("Docker environment validation failed")
            sys.exit(1)
    
    try:
        if args.command == "build":
            # Determine what to build
            build_dev = not args.prod_only
            build_prod = not args.dev_only
            
            success = build_docker_images(
                project_root=args.project_root,
                image_name=args.image_name,
                build_dev=build_dev,
                build_prod=build_prod,
                dockerfile_path=args.dockerfile
            )
            
            if not success:
                sys.exit(1)
                
        elif args.command == "list":
            images = list_docker_images(args.image_name)
            
            if images:
                print_step(f"Docker images for {args.image_name}")
                for image in images:
                    print_colored(f"  • {image}", "")
            else:
                print_colored(f"No Docker images found for {args.image_name}", "")
                
        elif args.command == "clean":
            success = clean_docker_images(
                image_name=args.image_name,
                confirm=not args.no_confirm
            )
            
            if not success:
                sys.exit(1)
    
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()