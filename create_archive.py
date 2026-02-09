#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create fara_crm_context.zip archive
Includes only specified file extensions and excludes .venv and node_modules folders
"""

import os
import zipfile
from pathlib import Path
from typing import List, Set


def should_exclude_path(path: Path, exclude_dirs: Set[str]) -> bool:
    """Check if path contains any excluded directories"""
    parts = path.parts
    return any(excluded in parts for excluded in exclude_dirs)


def find_files(
    source_dir: Path, extensions: List[str], exclude_dirs: Set[str]
) -> List[Path]:
    """Find all files with specified extensions, excluding certain directories"""
    files = []

    print("Searching for files...")
    print()

    for ext in extensions:
        for file_path in source_dir.rglob(ext):
            if file_path.is_file() and not should_exclude_path(
                file_path, exclude_dirs
            ):
                files.append(file_path)

    return files


def create_archive(
    source_dir: Path,
    output_zip: Path,
    extensions: List[str],
    exclude_dirs: Set[str],
):
    """Create ZIP archive with filtered files"""

    print("=" * 50)
    print("Creating fara_crm_context.zip archive")
    print("=" * 50)
    print()

    # Find all matching files
    files = find_files(source_dir, extensions, exclude_dirs)

    if not files:
        print("ERROR: No files found!")
        return False

    print(f"Found {len(files)} files")
    print()

    # Remove old archive if exists
    if output_zip.exists():
        print("Deleting old archive...")
        output_zip.unlink()

    # Create ZIP archive
    print("Creating ZIP archive...")
    print()

    try:
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                # Get relative path from source directory
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")

        print()
        print("=" * 50)
        print("SUCCESS: Archive created - fara_crm_context.zip")
        print("=" * 50)
        return True

    except Exception as e:
        print()
        print("=" * 50)
        print("ERROR:")
        print(str(e))
        print("=" * 50)
        return False


def main():
    """Main function"""

    # Configuration
    source_dir = Path(__file__).parent.resolve()
    output_zip = source_dir / "fara_crm_context.zip"

    extensions = [
        "*.py",
        "*.json",
        "*.ts",
        "*.tsx",
        "*.cjs",
        "*.lock",
        "*.css",
    ]

    exclude_dirs = {
        "mkdocs",
        "swagger_offlain",
        "filestore",
        "dist",
        ".venv",
        ".venv3.14",
        "node_modules",
        "__pycache__",
        ".git",
    }

    # Create archive
    success = create_archive(source_dir, output_zip, extensions, exclude_dirs)

    print()
    input("Press Enter to exit...")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
