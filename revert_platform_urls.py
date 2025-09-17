#!/usr/bin/env python3
"""
Script to revert console.anthropic.com URLs back to console.anthropic.com
across the entire repository.
"""

import os
import re
from pathlib import Path

# Define the replacements
REPLACEMENTS = [
    ('https://console.anthropic.com', 'https://console.anthropic.com'),
    ('console.anthropic.com', 'console.anthropic.com'),
]

# File extensions to process
EXTENSIONS = {
    '.py', '.md', '.json', '.ipynb', '.txt', '.yml', '.yaml',
    '.toml', '.sh', '.js', '.ts', '.jsx', '.tsx', '.html', '.css',
    '.env', '.example', '.rst', '.cfg', '.ini', '.conf'
}

# Directories to skip
SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    'env', '.tox', '.pytest_cache', 'dist', 'build', '.eggs'
}

def should_process_file(file_path):
    """Check if file should be processed."""
    path_obj = Path(file_path)

    # Check if any part of the path contains skip directories
    parts = path_obj.parts
    if any(skip_dir in parts for skip_dir in SKIP_DIRS):
        return False

    # Check extension
    file_ext = path_obj.suffix.lower()
    if file_ext in EXTENSIONS:
        return True

    # Also check files without extension or with .example suffix
    if str(path_obj).endswith('.example'):
        return True

    # Check for extensionless files like .env
    if file_ext == '' and path_obj.name.startswith('.'):
        return True

    return False

def process_file(file_path):
    """Process a single file and apply replacements."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        modified = False

        # Apply each replacement
        for old_text, new_text in REPLACEMENTS:
            if old_text in content:
                content = content.replace(old_text, new_text)
                modified = True

        # Write back if modified
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all files in the repository."""
    repo_root = Path(__file__).parent
    modified_files = []

    print(f"Scanning repository at: {repo_root}")
    print(f"Looking for files with console.anthropic.com URLs...\n")

    # Walk through all files
    for root, dirs, files in os.walk(repo_root):
        # Remove skip directories from dirs to prevent walking into them
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for file in files:
            file_path = Path(root) / file

            if should_process_file(file_path):
                if process_file(file_path):
                    rel_path = file_path.relative_to(repo_root)
                    modified_files.append(str(rel_path))
                    print(f"✓ Modified: {rel_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"{'='*60}")
    print(f"Total files modified: {len(modified_files)}")

    if modified_files:
        print(f"\nModified files:")
        for file in sorted(modified_files):
            print(f"  - {file}")

        print(f"\nReplacements made:")
        for old, new in REPLACEMENTS:
            print(f"  - '{old}' → '{new}'")
    else:
        print("No files were modified.")

if __name__ == "__main__":
    main()