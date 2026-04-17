#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
TEKTITE_ROOT = REPO_ROOT / "tektite-to-jastro"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def source_directories() -> list[Path]:
    return [
        path
        for path in sorted(TEKTITE_ROOT.iterdir(), key=lambda item: item.name.lower())
        if path.is_dir()
    ]


def build_payload(directory: Path) -> dict:
    images = [
        file
        for file in sorted(directory.iterdir(), key=lambda item: item.name.lower())
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return {
        "folder": directory.name,
        "path": directory.relative_to(REPO_ROOT).as_posix(),
        "imageCount": len(images),
        "images": [
            {
                "name": file.name,
                "extension": file.suffix.lower(),
                "sizeBytes": file.stat().st_size,
                "relativePath": file.relative_to(REPO_ROOT).as_posix(),
            }
            for file in images
        ],
    }


def write_if_changed(path: Path, content: str) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    if not TEKTITE_ROOT.exists():
        print("tektite-to-jastro folder not found.", file=sys.stderr)
        return 1

    changed = []
    for directory in source_directories():
        output_path = directory / "index.json"
        content = json.dumps(build_payload(directory), indent=2) + "\n"
        if write_if_changed(output_path, content):
            changed.append(output_path)

    if changed:
        print("Updated tektite indexes:")
        for path in changed:
            print(f"- {path.relative_to(REPO_ROOT).as_posix()}")
    else:
        print("Tektite indexes are already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
