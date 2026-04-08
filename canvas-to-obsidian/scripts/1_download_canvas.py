#!/usr/bin/env python3
"""
Canvas LMS Course Downloader
Downloads all course materials and saves them as organized markdown files.

Setup:
  1. Generate an API token: Canvas > Account > Settings > Approved Integrations > New Access Token
  2. Set CANVAS_URL and CANVAS_TOKEN (see usage below)

Usage:
  python canvas_downloader.py --url https://canvas.instructure.com --token YOUR_TOKEN
  python canvas_downloader.py --url https://canvas.instructure.com --token YOUR_TOKEN --course-id 12345
"""

import argparse
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from markdownify import markdownify as md

# ---------------------------------------------------------------------------
# Canvas API client
# ---------------------------------------------------------------------------

class CanvasClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.base_url}/api/v1{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    def paginate(self, path: str, params: dict = None) -> list:
        """Fetch all pages of a paginated Canvas endpoint."""
        results = []
        url = f"{self.base_url}/api/v1{path}"
        p = {"per_page": 100, **(params or {})}
        while url:
            resp = self.session.get(url, params=p, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
            # Follow Canvas Link: <next> header
            url = None
            p = {}  # params are embedded in the next URL
            link_header = resp.headers.get("Link", "")
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    match = re.search(r"<([^>]+)>", part)
                    if match:
                        url = match.group(1)
        return results

    def get_courses(self) -> list:
        return self.paginate("/courses", {"enrollment_state": "active", "include[]": "term"})

    def get_modules(self, course_id: int) -> list:
        return self.paginate(f"/courses/{course_id}/modules", {"include[]": "items"})

    def get_module_item_content(self, course_id: int, item: dict) -> str | None:
        """Return the HTML body of a Page module item, or None."""
        if item.get("type") != "Page":
            return None
        url_suffix = item.get("page_url") or item.get("url", "")
        if not url_suffix:
            return None
        # url_suffix may be a full URL or just the slug
        slug = url_suffix.split("/wiki/")[-1] if "/wiki/" in url_suffix else url_suffix.split("/")[-1]
        try:
            resp = self._get(f"/courses/{course_id}/pages/{slug}")
            return resp.json().get("body", "")
        except requests.HTTPError:
            return None

    def get_assignments(self, course_id: int) -> list:
        return self.paginate(f"/courses/{course_id}/assignments", {"include[]": "submission"})

    def get_announcements(self, course_id: int) -> list:
        return self.paginate("/announcements", {"context_codes[]": f"course_{course_id}"})

    def get_discussions(self, course_id: int) -> list:
        return self.paginate(f"/courses/{course_id}/discussion_topics")

    def get_discussion_full(self, course_id: int, topic_id: int) -> dict:
        resp = self._get(f"/courses/{course_id}/discussion_topics/{topic_id}/view")
        return resp.json()

    def get_files(self, course_id: int) -> list:
        return self.paginate(f"/courses/{course_id}/files")

    def download_file(self, url: str, dest: Path) -> None:
        resp = self.session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_filename(name: str, max_len: int = 80) -> str:
    """Sanitize a string so it is safe to use as a file/directory name."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:max_len] or "untitled"


def html_to_md(html: str) -> str:
    if not html:
        return ""
    return md(html, heading_style="ATX", bullets="-").strip()


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  Saved: {path}")


def is_slide_or_pdf(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in {".pdf", ".ppt", ".pptx", ".key", ".odp"}


# ---------------------------------------------------------------------------
# Downloader sections
# ---------------------------------------------------------------------------

def download_modules(client: CanvasClient, course_id: int, out_dir: Path) -> None:
    print("  Fetching modules / pages …")
    modules = client.get_modules(course_id)
    if not modules:
        print("    No modules found.")
        return

    for module in modules:
        mod_name = safe_filename(module.get("name", "module"))
        items = module.get("items", [])
        for item in items:
            item_type = item.get("type", "")
            item_title = safe_filename(item.get("title", "untitled"))

            if item_type == "Page":
                body = client.get_module_item_content(course_id, item)
                if body is not None:
                    content = f"# {item.get('title', 'Untitled')}\n\n{html_to_md(body)}"
                    write_md(out_dir / f"{mod_name}__{item_title}.md", content)
                time.sleep(0.1)

            elif item_type == "ExternalUrl":
                url = item.get("external_url", "")
                content = f"# {item.get('title', 'Untitled')}\n\n**External link:** {url}\n"
                write_md(out_dir / f"{mod_name}__{item_title}.md", content)

            elif item_type == "File":
                # Files are handled in download_files()
                pass


def download_files(client: CanvasClient, course_id: int, lectures_dir: Path, course_dir: Path) -> None:
    print("  Fetching files …")
    files = client.get_files(course_id)
    if not files:
        print("    No files found.")
        return

    for f in files:
        filename = f.get("display_name") or f.get("filename", "file")
        url = f.get("url")
        if not url:
            continue

        if is_slide_or_pdf(filename):
            dest = lectures_dir / safe_filename(filename)
        else:
            dest = course_dir / "files" / safe_filename(filename)

        if dest.exists():
            print(f"  Skipping (exists): {dest.name}")
            continue

        print(f"  Downloading: {filename}")
        try:
            client.download_file(url, dest)
        except requests.HTTPError as e:
            print(f"    Warning: could not download {filename}: {e}")
        time.sleep(0.15)


def download_assignments(client: CanvasClient, course_id: int, out_dir: Path) -> None:
    print("  Fetching assignments …")
    assignments = client.get_assignments(course_id)
    if not assignments:
        print("    No assignments found.")
        return

    for a in assignments:
        title = a.get("name", "untitled")
        fname = safe_filename(title)
        due = a.get("due_at") or "No due date"
        points = a.get("points_possible", "N/A")
        desc = html_to_md(a.get("description") or "")

        lines = [
            f"# {title}",
            "",
            f"**Due:** {due}  ",
            f"**Points:** {points}",
            "",
        ]
        if desc:
            lines += ["## Description", "", desc, ""]

        # Submission info
        sub = a.get("submission") or {}
        if sub:
            score = sub.get("score")
            grade = sub.get("grade")
            submitted_at = sub.get("submitted_at")
            if submitted_at:
                lines += [
                    "## My Submission",
                    "",
                    f"**Submitted:** {submitted_at}  ",
                    f"**Score:** {score}  ",
                    f"**Grade:** {grade}",
                    "",
                ]

        write_md(out_dir / f"{fname}.md", "\n".join(lines))
        time.sleep(0.05)


def download_announcements(client: CanvasClient, course_id: int, out_dir: Path) -> None:
    print("  Fetching announcements …")
    announcements = client.get_announcements(course_id)
    if not announcements:
        print("    No announcements found.")
        return

    for ann in announcements:
        title = ann.get("title", "untitled")
        fname = safe_filename(title)
        posted = ann.get("posted_at") or ann.get("created_at") or ""
        author = (ann.get("author") or {}).get("display_name", "Unknown")
        body = html_to_md(ann.get("message") or "")

        content = "\n".join([
            f"# {title}",
            "",
            f"**Posted:** {posted}  ",
            f"**Author:** {author}",
            "",
            body,
        ])
        write_md(out_dir / f"{fname}.md", content)
        time.sleep(0.05)


def _render_replies(replies: list, depth: int = 0) -> str:
    lines = []
    indent = "  " * depth
    for r in replies:
        author = (r.get("author") or {}).get("display_name", "Unknown")
        created = r.get("created_at", "")
        body = html_to_md(r.get("message") or "")
        lines.append(f"{indent}**{author}** ({created}):")
        for line in body.splitlines():
            lines.append(f"{indent}{line}")
        lines.append("")
        nested = r.get("replies") or []
        if nested:
            lines.append(_render_replies(nested, depth + 1))
    return "\n".join(lines)


def download_discussions(client: CanvasClient, course_id: int, out_dir: Path) -> None:
    print("  Fetching discussions …")
    topics = client.get_discussions(course_id)
    if not topics:
        print("    No discussions found.")
        return

    for topic in topics:
        title = topic.get("title", "untitled")
        fname = safe_filename(title)
        posted = topic.get("posted_at") or topic.get("created_at") or ""
        author = (topic.get("author") or {}).get("display_name", "Unknown")
        body = html_to_md(topic.get("message") or "")

        lines = [
            f"# {title}",
            "",
            f"**Posted:** {posted}  ",
            f"**Author:** {author}",
            "",
        ]
        if body:
            lines += ["## Prompt", "", body, ""]

        # Fetch threaded replies
        try:
            full = client.get_discussion_full(course_id, topic["id"])
            view = full.get("view") or []
            if view:
                lines += ["## Replies", "", _render_replies(view)]
        except requests.HTTPError:
            pass

        write_md(out_dir / f"{fname}.md", "\n".join(lines))
        time.sleep(0.2)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def process_course(client: CanvasClient, course: dict, output_root: Path) -> None:
    name = course.get("name") or course.get("course_code") or str(course["id"])
    course_id = course["id"]
    print(f"\n{'='*60}")
    print(f"Course: {name}  (id={course_id})")
    print(f"{'='*60}")

    course_dir = output_root / safe_filename(name)
    lectures_dir   = course_dir / "lectures"
    assignments_dir = course_dir / "assignments"
    announcements_dir = course_dir / "announcements"
    discussions_dir = course_dir / "discussions"

    for d in [lectures_dir, assignments_dir, announcements_dir, discussions_dir]:
        d.mkdir(parents=True, exist_ok=True)

    download_modules(client, course_id, lectures_dir)
    download_files(client, course_id, lectures_dir, course_dir)
    download_assignments(client, course_id, assignments_dir)
    download_announcements(client, course_id, announcements_dir)
    download_discussions(client, course_id, discussions_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Download all Canvas LMS course materials as markdown files."
    )
    parser.add_argument("--url",      required=True,  help="Canvas instance URL, e.g. https://canvas.instructure.com")
    parser.add_argument("--token",    required=True,  help="Canvas API access token")
    parser.add_argument("--course-id", type=int, default=None,
                        help="Download a single course by ID (omit to download all active courses)")
    parser.add_argument("--output",   default="canvas_courses",
                        help="Output root directory (default: ./canvas_courses)")
    args = parser.parse_args()

    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    client = CanvasClient(args.url, args.token)

    # Verify token works
    try:
        me = client._get("/users/self").json()
        print(f"Logged in as: {me.get('name', 'unknown')} ({me.get('login_id', '')})")
    except requests.HTTPError as e:
        print(f"Error: Could not authenticate. Check your --url and --token.\n{e}", file=sys.stderr)
        sys.exit(1)

    if args.course_id:
        try:
            course = client._get(f"/courses/{args.course_id}").json()
            process_course(client, course, output_root)
        except requests.HTTPError as e:
            print(f"Error fetching course {args.course_id}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        courses = client.get_courses()
        if not courses:
            print("No active courses found.")
            sys.exit(0)
        print(f"Found {len(courses)} active course(s).")
        for course in courses:
            try:
                process_course(client, course, output_root)
            except Exception as e:
                print(f"  Warning: failed to fully process course {course.get('id')}: {e}")

    print(f"\nDone. Files saved to: {output_root.resolve()}")


if __name__ == "__main__":
    main()
