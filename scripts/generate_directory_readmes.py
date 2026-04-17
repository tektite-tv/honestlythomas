#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}

FILE_TYPE_LABELS = {
    ".cname": "site configuration file",
    ".css": "stylesheet",
    ".gif": "GIF image",
    ".html": "HTML document",
    ".jpeg": "JPEG image",
    ".jpg": "JPEG image",
    ".js": "JavaScript file",
    ".json": "JSON file",
    ".md": "Markdown document",
    ".png": "PNG image",
    ".py": "Python script",
    ".svg": "SVG image",
    ".toml": "TOML file",
    ".txt": "text file",
    ".webp": "WebP image",
    ".xml": "XML file",
    ".yaml": "YAML file",
    ".yml": "YAML file",
}

EXACT_FILE_LABELS = {
    "cname": "site configuration file",
    "dockerfile": "Docker build file",
    "license": "license file",
    "makefile": "build script",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate README.md files for every directory in the repository."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing files when generated README content differs.",
    )
    return parser.parse_args()


def should_skip_dir(path: Path) -> bool:
    return path.name in SKIP_DIR_NAMES


def iter_directories(root: Path) -> list[Path]:
    directories = [root]
    for path in sorted(root.rglob("*")):
        if not path.is_dir():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        directories.append(path)
    return directories


def relative_label(path: Path) -> str:
    if path == REPO_ROOT:
        return "/"
    return path.relative_to(REPO_ROOT).as_posix()


def extension_label(path: Path) -> str:
    exact_name = path.name.lower()
    if exact_name in EXACT_FILE_LABELS:
        return EXACT_FILE_LABELS[exact_name]
    suffix = path.suffix.lower()
    if suffix in FILE_TYPE_LABELS:
        return FILE_TYPE_LABELS[suffix]
    if suffix:
        return f"{suffix[1:].upper()} file"
    return "file without extension"


def file_type_key(path: Path) -> str:
    exact_name = path.name.lower()
    if exact_name in EXACT_FILE_LABELS:
        return EXACT_FILE_LABELS[exact_name]
    suffix = path.suffix.lower()
    if suffix in FILE_TYPE_LABELS:
        return FILE_TYPE_LABELS[suffix]
    if suffix:
        return f"{suffix[1:].upper()} file"
    return "extensionless file"


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def summarize_directory_kind(directory: Path, files: list[Path], subdirs: list[Path]) -> str:
    extensions = Counter(file.suffix.lower() or "[none]" for file in files)
    image_count = sum(count for ext, count in extensions.items() if ext in IMAGE_EXTENSIONS)
    textish_count = sum(
        count for ext, count in extensions.items() if ext in {".md", ".html", ".css", ".js", ".json", ".py", ".txt"}
    )

    if files and image_count == len(files):
        return "This folder primarily stores image assets."
    if files and textish_count == len(files):
        return "This folder primarily stores text or source files."
    if subdirs and not files:
        return "This folder is mainly an index of nested directories."
    if not files and not subdirs:
        return "This folder is currently empty."
    return "This folder groups together the files and subdirectories listed below."


def build_readme(directory: Path) -> str:
    children = sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
    subdirs = [child for child in children if child.is_dir() and not should_skip_dir(child)]
    files = [
        child
        for child in children
        if child.is_file() and child.name.lower() != "readme.md"
    ]

    file_type_counts = Counter(file_type_key(file) for file in files)
    file_type_summary = ", ".join(
        f"{count} {label}"
        for label, count in sorted(file_type_counts.items(), key=lambda item: item[0])
    )

    title = directory.name if directory != REPO_ROOT else REPO_ROOT.name
    location = relative_label(directory)
    lines = [
        f"# {title}",
        "",
        f"Auto-generated directory guide for `{location}`.",
        "",
        summarize_directory_kind(directory, files, subdirs),
        "",
        f"- Subdirectories: {len(subdirs)}",
        f"- Files: {len(files)}",
    ]

    if files:
        lines.append(f"- File types: {file_type_summary}")

    lines.extend(["", "## Contents", ""])

    if subdirs:
        lines.append("### Subdirectories")
        lines.append("")
        for subdir in subdirs:
            nested_files = [
                path
                for path in subdir.rglob("*")
                if path.is_file()
                and path.name.lower() != "readme.md"
                and not any(part in SKIP_DIR_NAMES for part in path.relative_to(subdir).parts)
            ]
            lines.append(
                f"- [{subdir.name}]({subdir.name}/README.md) - contains {len(nested_files)} file(s) beneath this folder."
            )
        lines.append("")

    if files:
        lines.append("### Files")
        lines.append("")
        for file in files:
            lines.append(
                f"- `{file.name}` - {extension_label(file)}, {human_size(file.stat().st_size)}."
            )
        lines.append("")

    if not subdirs and not files:
        lines.append("No files or subdirectories are currently present.")
        lines.append("")

    lines.append("> This README is generated by `scripts/generate_directory_readmes.py`.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    changed_files: list[Path] = []

    for directory in iter_directories(REPO_ROOT):
        readme_path = directory / "README.md"
        new_content = build_readme(directory)
        current_content = readme_path.read_text(encoding="utf-8") if readme_path.exists() else None

        if current_content == new_content:
            continue

        changed_files.append(readme_path)
        if not args.check:
            readme_path.write_text(new_content, encoding="utf-8")

    if args.check and changed_files:
        print("README files are out of date:")
        for path in changed_files:
            print(f"- {path.relative_to(REPO_ROOT).as_posix()}")
        return 1

    if not args.check:
        if changed_files:
            print("Updated README files:")
            for path in changed_files:
                print(f"- {path.relative_to(REPO_ROOT).as_posix()}")
        else:
            print("README files are already up to date.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
