#!/usr/bin/env python3
"""
convert_slides.py
-----------------
Converts downloaded PDF/PPTX slide files into structured Obsidian notes.

SETUP:
  1. Download slides from Canvas (browser → course → Files or lecture pages)
  2. Drop them into ~/Desktop/slides/ organised by course code:
       slides/
         ICT211/   ← Database Design slides
         ICT200/   ← Systems Analysis slides
         ICT220/   ← Wireless Communications slides
         ICT221/   ← OOP slides
  3. Run: python3 convert_slides.py

Each PDF/PPTX gets a Slides Notes.md written into the matching week folder.
If the week can't be detected from the filename, it's saved in a
_Unmatched/ folder for you to manually place.

Usage:
    python3 convert_slides.py
    python3 convert_slides.py --course ICT211
    python3 convert_slides.py --dry-run
    python3 convert_slides.py --slides-dir ~/Downloads/my_slides
"""

import argparse
import re
import sys
import subprocess
from pathlib import Path

import pymupdf4llm
import anthropic

VAULT      = Path.home() / "Desktop" / "University"
SLIDES_DIR = Path.home() / "Desktop" / "slides"

CODE_TO_NAME = {
    "ICT200": "Systems Analysis and Design",
    "ICT211": "Database Design",
    "ICT220": "Wireless Communications",
    "ICT221": "Object-Oriented Programming",
}

WEEK_RE = re.compile(r'[Ww]eek[_\s\-]+(\d+)', re.IGNORECASE)
MOD_RE  = re.compile(r'[Mm]od(?:ule)?[_\s\-]+(\d+)', re.IGNORECASE)


# ── PPTX → PDF conversion (uses LibreOffice if available, else warns) ─────────

def pptx_to_pdf(pptx: Path) -> Path | None:
    """Convert PPTX to PDF using LibreOffice. Returns PDF path or None."""
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", str(pptx.parent), str(pptx)],
            check=True, capture_output=True, timeout=60
        )
        pdf = pptx.with_suffix(".pdf")
        return pdf if pdf.exists() else None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


# ── PDF → markdown ────────────────────────────────────────────────────────────

def pdf_to_markdown(pdf: Path) -> str:
    """Extract markdown text from PDF using pymupdf4llm."""
    try:
        md = pymupdf4llm.to_markdown(str(pdf))
        # Clean up common PDF artifacts
        md = re.sub(r'\n{4,}', '\n\n\n', md)
        md = re.sub(r'-----+', '---', md)
        return md.strip()
    except Exception as e:
        return f"*(Could not extract text: {e})*"


# ── Claude note generation ────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a university note-taker. Given raw text extracted from lecture slides, \
produce clean structured Markdown study notes. Slides often have incomplete \
sentences — infer meaning from context. Use ## headings for each slide section, \
bullet points for key ideas, **bold** for important terms, and ```code blocks``` \
for any code or formulas. Do NOT include slide numbers or layout artifacts. \
Output only the markdown content."""

def generate_slide_notes(client: anthropic.Anthropic,
                         raw_md: str,
                         code: str,
                         week_num: int | None,
                         week_topic: str,
                         filename: str) -> str:
    context = f"Week {week_num} — {week_topic}" if week_num else filename

    prompt = f"""\
Course: {code} — {CODE_TO_NAME.get(code, code)}
Slides: {context}
Filename: {filename}

RAW SLIDE CONTENT (first 14000 chars):
{raw_md[:14000]}

Generate structured study notes from these slides.
Include:
1. ## Overview — what this lecture covers
2. ## Key Concepts — the main ideas, one bullet per slide/section
3. ## Important Terms — **term**: definition for any defined terms
4. ## Diagrams / Figures — describe any important diagrams mentioned
5. ## Key Takeaways — 3-5 most exam-relevant points
"""
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT,
    )
    return msg.content[0].text.strip()


# ── Week folder matching ──────────────────────────────────────────────────────

def detect_week(filename: str) -> int | None:
    m = WEEK_RE.search(filename) or MOD_RE.search(filename)
    return int(m.group(1)) if m else None


def find_week_folder(code: str, week_num: int) -> Path | None:
    course_dirs = list((VAULT / "Courses").glob(f"{code} — *"))
    if not course_dirs:
        return None
    cdir = course_dirs[0]
    for d in cdir.iterdir():
        if d.is_dir() and d.name.startswith(f"Week {week_num} —"):
            return d
    return None


def week_topic_from_folder(folder: Path) -> str:
    m = re.match(r'Week \d+ — (.+)', folder.name)
    return m.group(1) if m else ""


# ── Output writer ─────────────────────────────────────────────────────────────

def write_slide_notes(dest_dir: Path, code: str, week_num: int | None,
                      topic: str, filename: str,
                      notes_md: str, raw_md: str) -> Path:
    out = dest_dir / "Slide Notes.md"
    name = CODE_TO_NAME.get(code, code)

    week_str = f"Week {week_num} — {topic}" if week_num else filename

    if out.exists():
        # Append additional slide file as a new section
        existing = out.read_text(encoding="utf-8")
        section  = f"\n\n---\n\n## Slides: {filename}\n\n{notes_md}"
        out.write_text(existing + section, encoding="utf-8")
    else:
        header = f"""\
# {week_str} — Slide Notes

**Course:** [[../{code} — {name}|{code} — {name}]]
**Source:** {filename}
**Tags:** #{code.lower()} #week{week_num or 'X'} #slides #lecture

---

"""
        out.write_text(header + notes_md, encoding="utf-8")

    # Also save the raw extracted text for reference
    raw_out = dest_dir / f"_raw_{Path(filename).stem}.md"
    raw_out.write_text(f"# Raw extraction — {filename}\n\n```\n{raw_md[:8000]}\n```\n",
                       encoding="utf-8")

    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def collect_slides(slides_root: Path, course_filter: str | None) -> list[dict]:
    items = []
    for code_dir in sorted(slides_root.iterdir()):
        if not code_dir.is_dir():
            continue
        code = code_dir.name.upper()
        if course_filter and code != course_filter.upper():
            continue
        if code not in CODE_TO_NAME:
            print(f"  Warning: unknown course folder '{code_dir.name}' — skipping.")
            continue

        for f in sorted(code_dir.iterdir()):
            if f.suffix.lower() not in (".pdf", ".ppt", ".pptx", ".key"):
                continue
            items.append({"path": f, "code": code})

    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--course",     help="e.g. ICT211")
    parser.add_argument("--slides-dir", type=Path, default=SLIDES_DIR)
    args = parser.parse_args()

    slides_root = args.slides_dir
    if not slides_root.exists():
        print(f"Slides directory not found: {slides_root}")
        print("Create it and add subfolders per course code, e.g.:")
        print("  ~/Desktop/slides/ICT211/Week1_DB_Intro.pdf")
        sys.exit(1)

    slides = collect_slides(slides_root, args.course)
    if not slides:
        print("No slide files found.")
        sys.exit(0)

    print(f"Found {len(slides)} slide file(s).\n")

    if args.dry_run:
        for s in slides:
            wn    = detect_week(s["path"].name)
            wdir  = find_week_folder(s["code"], wn) if wn else None
            label = wdir.name if wdir else "✗ no week match → _Unmatched/"
            print(f"  [{s['code']}] {s['path'].name}  →  {label}")
        return

    client = anthropic.Anthropic()
    ok = 0

    for i, s in enumerate(slides, 1):
        f    = s["path"]
        code = s["code"]
        print(f"[{i}/{len(slides)}] {code} — {f.name}")

        # Convert PPTX → PDF if needed
        pdf = f
        if f.suffix.lower() in (".ppt", ".pptx", ".key"):
            print("  Converting to PDF…")
            pdf = pptx_to_pdf(f)
            if not pdf:
                print("  ✗ LibreOffice not available — install it to process PPTX files.")
                print("    Install: brew install --cask libreoffice")
                print("    Or export to PDF manually from PowerPoint.\n")
                continue

        # Extract markdown from PDF
        print("  Extracting text from PDF…")
        raw_md = pdf_to_markdown(pdf)
        if not raw_md or len(raw_md) < 50:
            print("  ✗ Could not extract readable text (may be image-based PDF).\n")
            continue
        print(f"  ✓ Extracted {len(raw_md)} chars")

        # Detect week
        wn   = detect_week(f.name)
        wdir = find_week_folder(code, wn) if wn else None

        if wdir:
            topic = week_topic_from_folder(wdir)
            print(f"  Matched → {wdir.name}")
        else:
            # Save to _Unmatched folder
            unmatched = VAULT / "Courses" / next(
                (d.name for d in (VAULT / "Courses").iterdir() if d.name.startswith(code)), code
            ) / "_Unmatched"
            unmatched.mkdir(parents=True, exist_ok=True)
            wdir  = unmatched
            topic = f.stem
            print(f"  No week match → saving to _Unmatched/")

        # Generate notes with Claude
        print("  Generating notes with Claude…")
        try:
            notes = generate_slide_notes(client, raw_md, code, wn, topic, f.name)
        except anthropic.APIError as e:
            print(f"  ✗ Claude error: {e}\n")
            continue

        out = write_slide_notes(wdir, code, wn, topic, f.name, notes, raw_md)
        print(f"  ✓ Saved → {out.relative_to(VAULT)}\n")
        ok += 1

    print(f"Done — {ok}/{len(slides)} slides converted.")


if __name__ == "__main__":
    main()
