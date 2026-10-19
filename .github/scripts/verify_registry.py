#!/usr/bin/env python3
"""
Verify authors.yaml and registry.yaml integrity:
1. GitHub handles exist
2. Website and avatar URLs are valid
3. All registry.yaml authors are defined in authors.yaml
4. All registry.yaml paths exist

Usage:
    python verify_registry.py [command]

Commands:
    all          Run all verifications (default)
    authors      Verify GitHub handles and author URLs only
    paths        Verify registry paths only
    registry     Verify registry authors exist in authors.yaml
    schema       Verify YAML files match their JSON schemas
"""

import json
import sys
from pathlib import Path

import requests
import yaml

try:
    from jsonschema import ValidationError, validate

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def check_github_handle(username):
    """Check if a GitHub handle exists."""
    try:
        response = requests.head(f"https://github.com/{username}", timeout=10, allow_redirects=True)
        if response.status_code == 404:
            return False, "GitHub profile not found"
        elif response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        return True, None
    except requests.RequestException as e:
        return False, str(e)


def check_url(url):
    """Check if a URL is accessible."""
    # Skip x.com URLs as they block HEAD requests
    if "x.com" in url:
        return True, "skipped (x.com)"

    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        return True, None
    except requests.RequestException as e:
        return False, str(e)


def verify_authors(authors):
    """Verify GitHub handles and author URLs."""
    failed_handles = []
    failed_urls = []

    # Verify GitHub handles
    print("=== Verifying GitHub Handles ===\n")
    for username in authors.keys():
        print(f"Checking GitHub handle: {username}...")
        success, error = check_github_handle(username)
        if not success:
            failed_handles.append(f"{username} ({error})")
            print(f"  ❌ {error}")
        else:
            print("  ✓ OK")

    # Verify URLs
    print("\n=== Verifying Author URLs ===\n")
    for username, details in authors.items():
        print(f"Checking URLs for {username}...")

        # Check website URL
        if "website" in details:
            url = details["website"]
            success, error = check_url(url)
            if not success:
                failed_urls.append(f"{username}.website: {url} ({error})")
                print(f"  ❌ Website URL: {url} ({error})")
            elif error:
                print(f"  ⊘ Website URL {error}: {url}")
            else:
                print(f"  ✓ Website URL OK: {url}")

        # Check avatar URL
        if "avatar" in details:
            url = details["avatar"]
            success, error = check_url(url)
            if not success:
                failed_urls.append(f"{username}.avatar: {url} ({error})")
                print(f"  ❌ Avatar URL: {url} ({error})")
            elif error:
                print(f"  ⊘ Avatar URL {error}: {url}")
            else:
                print(f"  ✓ Avatar URL OK: {url}")

    return failed_handles, failed_urls


def verify_registry_authors(registry, authors):
    """Verify registry authors exist in authors.yaml."""
    missing_authors = []

    print("\n=== Verifying Registry Authors ===\n")
    registry_authors = set()
    for entry in registry:
        if "authors" in entry:
            for author in entry["authors"]:
                registry_authors.add(author)

    print(f"Found {len(registry_authors)} unique authors in registry.yaml")

    for author in sorted(registry_authors):
        if author not in authors:
            missing_authors.append(author)
            print(f"  ❌ Author '{author}' not found in authors.yaml")
        else:
            print(f"  ✓ {author}")

    return missing_authors


def verify_paths(registry, repo_root):
    """Verify registry paths exist."""
    missing_paths = []

    print("\n=== Verifying Registry Paths ===\n")
    print(f"Found {len(registry)} cookbooks in registry.yaml")

    for entry in registry:
        if "path" in entry:
            path = entry["path"]
            full_path = repo_root / path
            title = entry.get("title", "Unknown")

            if not full_path.exists():
                missing_paths.append(f"{path} (title: {title})")
                print(f"  ❌ Path not found: {path}")
            else:
                print(f"  ✓ {path}")
        else:
            missing_paths.append(
                f"Entry missing 'path' field (title: {entry.get('title', 'Unknown')})"
            )
            print(f"  ❌ Entry missing 'path' field: {entry.get('title', 'Unknown')}")

    return missing_paths


def verify_schemas(repo_root, authors, registry):
    """Verify YAML files match their JSON schemas."""
    if not HAS_JSONSCHEMA:
        print("\n⚠️  Skipping schema validation (jsonschema not installed)")
        return []

    schema_errors = []

    print("\n=== Verifying JSON Schemas ===\n")

    # Verify authors.yaml against schema
    authors_schema_path = repo_root / ".github" / "authors_schema.json"
    if authors_schema_path.exists():
        print("Checking authors.yaml against schema...")
        try:
            with open(authors_schema_path) as f:
                authors_schema = json.load(f)
            validate(instance=authors, schema=authors_schema)
            print("  ✓ authors.yaml matches schema")
        except ValidationError as e:
            path_str = ".".join(str(p) for p in e.path) if e.path else "root"
            schema_errors.append(f"authors.yaml: {e.message} at {path_str}")
            print(f"  ❌ authors.yaml schema validation failed: {e.message}")
            if e.path:
                print(f"     at path: {path_str}")
        except json.JSONDecodeError as e:
            schema_errors.append(f"authors_schema.json: Invalid JSON - {e}")
            print(f"  ❌ authors_schema.json is invalid: {e}")
    else:
        print("  ⊘ authors_schema.json not found, skipping")

    # Verify registry.yaml against schema
    registry_schema_path = repo_root / ".github" / "registry_schema.json"
    if registry_schema_path.exists():
        print("\nChecking registry.yaml against schema...")
        try:
            with open(registry_schema_path) as f:
                registry_schema = json.load(f)
            validate(instance=registry, schema=registry_schema)
            print("  ✓ registry.yaml matches schema")
        except ValidationError as e:
            path_str = ".".join(str(p) for p in e.path) if e.path else "root"
            schema_errors.append(f"registry.yaml: {e.message} at {path_str}")
            print(f"  ❌ registry.yaml schema validation failed: {e.message}")
            if e.path:
                print(f"     at path: {path_str}")
        except json.JSONDecodeError as e:
            schema_errors.append(f"registry_schema.json: Invalid JSON - {e}")
            print(f"  ❌ registry_schema.json is invalid: {e}")
    else:
        print("  ⊘ registry_schema.json not found, skipping")

    return schema_errors


def main():
    # Parse command line argument
    command = sys.argv[1] if len(sys.argv) > 1 else "all"

    if command not in ["all", "authors", "paths", "registry", "schema"]:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    # Load YAML files
    repo_root = Path(__file__).parent.parent.parent
    authors_path = repo_root / "authors.yaml"
    registry_path = repo_root / "registry.yaml"

    authors = None
    registry = None

    if command in ["all", "authors", "registry", "schema"]:
        with open(authors_path) as f:
            authors = yaml.safe_load(f)

    if command in ["all", "paths", "registry", "schema"]:
        with open(registry_path) as f:
            registry = yaml.safe_load(f)

    # Run verifications based on command
    failed_handles = []
    failed_urls = []
    missing_authors = []
    missing_paths = []
    schema_errors = []

    if command in ["all", "authors"]:
        failed_handles, failed_urls = verify_authors(authors)

    if command in ["all", "registry"]:
        missing_authors = verify_registry_authors(registry, authors)

    if command in ["all", "paths"]:
        missing_paths = verify_paths(registry, repo_root)

    if command in ["all", "schema"]:
        schema_errors = verify_schemas(repo_root, authors, registry)

    # Report results
    has_failures = False

    if failed_handles:
        print("\n❌ The following GitHub handles failed verification:")
        for handle in failed_handles:
            print(f"  - {handle}")
        has_failures = True

    if failed_urls:
        print("\n❌ The following URLs failed verification:")
        for url in failed_urls:
            print(f"  - {url}")
        has_failures = True

    if missing_authors:
        print("\n❌ The following authors are in registry.yaml but not in authors.yaml:")
        for author in missing_authors:
            print(f"  - {author}")
        has_failures = True

    if missing_paths:
        print("\n❌ The following paths in registry.yaml do not exist:")
        for path in missing_paths:
            print(f"  - {path}")
        has_failures = True

    if schema_errors:
        print("\n❌ The following schema validation errors occurred:")
        for error in schema_errors:
            print(f"  - {error}")
        has_failures = True

    if has_failures:
        sys.exit(1)
    else:
        print("\n✓ All verifications passed successfully!")


if __name__ == "__main__":
    main()
