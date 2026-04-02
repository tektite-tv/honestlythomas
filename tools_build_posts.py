#!/usr/bin/env python3
"""Build a post manifest for a static blog hosted on GitHub Pages."""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "posts.json"
ALLOWED_EXTENSIONS = {".md", ".txt", ".html"}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\.[a-z0-9]+$", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "untitled"


def html_body_only(raw_html: str) -> str:
    match = re.search(r"<body[^>]*>(.*?)</body>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else raw_html.strip()


def markdown_to_html(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    html_parts: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False
    code_lines: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            html_parts.append(f"<p>{inline_markdown(' '.join(paragraph_lines).strip())}</p>")
            paragraph_lines = []

    def flush_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        if in_ol:
            html_parts.append("</ol>")
            in_ol = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_lists()
            if in_code:
                html_parts.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_lists()
            level = len(heading.group(1))
            html_parts.append(f"<h{level}>{inline_markdown(heading.group(2).strip())}</h{level}>")
            continue

        blockquote = re.match(r"^>\s?(.*)$", stripped)
        if blockquote:
            flush_paragraph()
            flush_lists()
            html_parts.append(f"<blockquote><p>{inline_markdown(blockquote.group(1))}</p></blockquote>")
            continue

        unordered = re.match(r"^[-*+]\s+(.*)$", stripped)
        if unordered:
            flush_paragraph()
            if in_ol:
                html_parts.append("</ol>")
                in_ol = False
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            html_parts.append(f"<li>{inline_markdown(unordered.group(1))}</li>")
            continue

        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered:
            flush_paragraph()
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            if not in_ol:
                html_parts.append("<ol>")
                in_ol = True
            html_parts.append(f"<li>{inline_markdown(ordered.group(1))}</li>")
            continue

        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_lists()

    if in_code:
        html_parts.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))

    return "\n".join(html_parts)


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", lambda m: f"<code>{html.escape(m.group(1))}</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def text_to_html(text: str) -> str:
    paragraphs = [block.strip() for block in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n") if block.strip()]
    return "\n".join(f"<p>{html.escape(p).replace(chr(10), '<br />')}</p>" for p in paragraphs)


def strip_tags(html_text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def derive_title(path: Path, raw_text: str, ext: str) -> str:
    if ext == ".md":
        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    if ext == ".html":
        title_match = re.search(r"<title>(.*?)</title>", raw_text, flags=re.IGNORECASE | re.DOTALL)
        if title_match and title_match.group(1).strip():
            return re.sub(r"\s+", " ", title_match.group(1)).strip()
        heading_match = re.search(r"<h1[^>]*>(.*?)</h1>", raw_text, flags=re.IGNORECASE | re.DOTALL)
        if heading_match and strip_tags(heading_match.group(1)).strip():
            return strip_tags(heading_match.group(1)).strip()
    if ext == ".txt":
        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:120]
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def get_last_commit_date(path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout.strip()
        if value:
            return value
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def build_post(path: Path) -> dict:
    ext = path.suffix.lower()
    raw_text = path.read_text(encoding="utf-8")

    if ext == ".md":
        content_html = markdown_to_html(raw_text)
    elif ext == ".txt":
        content_html = text_to_html(raw_text)
    else:
        content_html = html_body_only(raw_text)

    text_content = strip_tags(content_html)
    title = derive_title(path, raw_text, ext)
    slug = slugify(path.relative_to(POSTS_DIR).as_posix())
    excerpt = (text_content[:280] + "...") if len(text_content) > 280 else text_content

    return {
        "title": title,
        "slug": slug,
        "date": get_last_commit_date(path),
        "ext": ext.lstrip("."),
        "source_path": path.relative_to(ROOT).as_posix(),
        "excerpt": excerpt,
        "text_content": text_content,
        "content_html": content_html,
        "tags": [],
    }


def iter_post_files() -> Iterable[Path]:
    for path in sorted(POSTS_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
            yield path


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    posts = [build_post(path) for path in iter_post_files()]
    posts.sort(key=lambda item: item["date"], reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "posts": posts,
    }

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE} with {len(posts)} posts")


if __name__ == "__main__":
    main()
