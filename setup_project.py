#!/usr/bin/env python3
"""
Interactive project setup script.

This script helps you configure your new project by replacing placeholder values
with your actual configuration. Run it after creating a new project from the template.

Usage:
    python setup_project.py          # Interactive mode - prompts for each placeholder
    python setup_project.py --check  # Check mode - only shows remaining placeholders
"""

import os
import re
import sys
from pathlib import Path

# Placeholder definitions with descriptions and examples
PLACEHOLDERS = {
    "dapnodered": {
        "description": "Your project name (used for display in UI)",
        "example": "My Awesome App",
    },
    "{{PROJECT_DOMAIN}}": {
        "description": "Your project domain",
        "example": "myapp.example.com",
    },
    "{{HARBOR_PATH}}": {
        "description": "Harbor registry path for backend",
        "example": "dap-api/my-awesome-app",
    },
    "{{HARBOR_PATH_UI}}": {
        "description": "Harbor registry path for frontend",
        "example": "dap-ui/my-awesome-app",
    },
    "{{AZURE_CLIENT_ID}}": {
        "description": "Azure AD Application Client ID",
        "example": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    },
    "{{AZURE_TENANT_ID}}": {
        "description": "Azure AD Tenant ID",
        "example": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    },
    "{{SENTRY_DSN}}": {
        "description": "Sentry DSN for error tracking (leave empty to disable)",
        "example": "https://xxx@sentry.example.com/1",
    },
    "{{BRAND_COLOR}}": {
        "description": "Primary brand color (hex)",
        "example": "#ce003c",
    },
}

# File extensions to process
EXTENSIONS = {
    ".py", ".ts", ".tsx", ".vue", ".json", ".yml", ".yaml",
    ".md", ".scss", ".css", ".html", ".sh", ".env", ".example"
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "dist", "build",
    ".venv", "venv", ".pytest_cache", ".mypy_cache"
}


def get_project_root() -> Path:
    """Get the project root directory."""
    # If running from /workspace, use that
    if Path("/workspace").exists() and Path("/workspace/setup_project.py").exists():
        return Path("/workspace")
    # Otherwise use the script's directory
    return Path(__file__).parent


def should_process_file(file_path: Path) -> bool:
    """Check if a file should be processed."""
    # Check extension
    if file_path.suffix not in EXTENSIONS and file_path.name not in {"Dockerfile", "Dockerfile.dev", "Dockerfile.prod"}:
        # Also check for files like .env.example
        if not any(file_path.name.endswith(ext) for ext in EXTENSIONS):
            return False

    # Check if in skip directory
    for part in file_path.parts:
        if part in SKIP_DIRS:
            return False

    return True


def find_placeholders_in_file(file_path: Path) -> set:
    """Find all placeholders in a file."""
    placeholders = set()
    try:
        content = file_path.read_text(encoding="utf-8")
        # Find all {{SOMETHING}} patterns
        matches = re.findall(r"\{\{[A-Z_]+\}\}", content)
        placeholders.update(matches)
    except (UnicodeDecodeError, PermissionError):
        pass
    return placeholders


def find_all_placeholders(root: Path) -> dict:
    """Find all placeholders and which files contain them."""
    placeholder_files = {}

    for file_path in root.rglob("*"):
        if file_path.is_file() and should_process_file(file_path):
            placeholders = find_placeholders_in_file(file_path)
            for placeholder in placeholders:
                if placeholder not in placeholder_files:
                    placeholder_files[placeholder] = []
                placeholder_files[placeholder].append(file_path)

    return placeholder_files


def replace_in_file(file_path: Path, placeholder: str, value: str) -> bool:
    """Replace a placeholder in a file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if placeholder in content:
            new_content = content.replace(placeholder, value)
            file_path.write_text(new_content, encoding="utf-8")
            return True
    except (UnicodeDecodeError, PermissionError) as e:
        print(f"  Warning: Could not process {file_path}: {e}")
    return False


def print_header():
    """Print the script header."""
    print("\n" + "=" * 60)
    print("  Project Setup - Configure Placeholders")
    print("=" * 60 + "\n")


def print_remaining_placeholders(placeholder_files: dict):
    """Print remaining placeholders that need configuration."""
    if not placeholder_files:
        print("✓ All placeholders have been configured!")
        return

    print(f"Found {len(placeholder_files)} placeholder(s) to configure:\n")

    for placeholder, files in sorted(placeholder_files.items()):
        info = PLACEHOLDERS.get(placeholder, {"description": "Unknown", "example": "N/A"})
        print(f"  • {placeholder}")
        print(f"    {info['description']}")
        print(f"    Example: {info['example']}")
        print(f"    Found in {len(files)} file(s)")
        print()


def check_mode(root: Path):
    """Check mode - only show remaining placeholders."""
    print_header()
    placeholder_files = find_all_placeholders(root)

    # Filter to only known placeholders
    known_placeholders = {p: f for p, f in placeholder_files.items() if p in PLACEHOLDERS}

    if known_placeholders:
        print("⚠ There are unconfigured placeholders in this project.\n")
        print_remaining_placeholders(known_placeholders)
        print("Run 'python setup_project.py' to configure them interactively.\n")
    else:
        print("✓ All placeholders have been configured!\n")


def interactive_mode(root: Path):
    """Interactive mode - prompt for each placeholder."""
    print_header()

    placeholder_files = find_all_placeholders(root)

    # Filter to only known placeholders
    known_placeholders = {p: f for p, f in placeholder_files.items() if p in PLACEHOLDERS}

    if not known_placeholders:
        print("✓ All placeholders have been configured!")
        print("  Your project is ready to use.\n")
        return

    print(f"Found {len(known_placeholders)} placeholder(s) to configure.\n")
    print("For each placeholder, enter your value or press Enter to skip.\n")
    print("-" * 60 + "\n")

    replacements = {}
    skipped = []

    for placeholder in sorted(known_placeholders.keys()):
        info = PLACEHOLDERS[placeholder]
        files = known_placeholders[placeholder]

        print(f"Placeholder: {placeholder}")
        print(f"Description: {info['description']}")
        print(f"Example:     {info['example']}")
        print(f"Found in:    {len(files)} file(s)")

        value = input(f"Enter value (or Enter to skip): ").strip()

        if value:
            replacements[placeholder] = value
            print(f"  → Will replace with: {value}")
        else:
            skipped.append(placeholder)
            print("  → Skipped")

        print()

    # Perform replacements
    if replacements:
        print("-" * 60)
        print("\nApplying replacements...\n")

        for placeholder, value in replacements.items():
            files = known_placeholders[placeholder]
            replaced_count = 0

            for file_path in files:
                if replace_in_file(file_path, placeholder, value):
                    replaced_count += 1

            print(f"  ✓ {placeholder} → {value}")
            print(f"    Updated {replaced_count} file(s)")

        print()

    # Summary
    print("=" * 60)
    print("  Summary")
    print("=" * 60 + "\n")

    if replacements:
        print(f"✓ Replaced {len(replacements)} placeholder(s)")

    if skipped:
        print(f"⚠ Skipped {len(skipped)} placeholder(s):")
        for p in skipped:
            print(f"    • {p}")
        print("\n  Run this script again to configure skipped placeholders.")

    if not skipped:
        print("\n✓ All placeholders configured! Your project is ready.")

    print()


def main():
    root = get_project_root()

    if "--check" in sys.argv:
        check_mode(root)
    else:
        interactive_mode(root)


if __name__ == "__main__":
    main()
