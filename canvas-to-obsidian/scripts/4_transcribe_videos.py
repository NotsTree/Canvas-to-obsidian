#!/usr/bin/env python3
"""
transcribe_videos.py
--------------------
Finds every YouTube link in the Obsidian vault, fetches its transcript,
uses Claude to generate structured notes, then writes a Video Notes.md
into the matching week folder.

Usage:
    python3 transcribe_videos.py
    python3 transcribe_videos.py --dry-run      # show what would be processed
    python3 transcribe_videos.py --course ICT211 # one course only
"""

import argparse
import re
import sys
import time
from pathlib import Path

import anthropic
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

_yt = YouTubeTranscriptApi()   # v1.x requires instantiation

VAULT   = Path.home() / "Desktop" / "University"
COURSES = Path.home() / "Desktop" / "canvas_courses"

YOUTUBE_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})')


# ── Transcript fetching ───────────────────────────────────────────────────────

def get_transcript(video_id: str) -> list[dict] | None:
    """Return list of {text, start, duration} dicts, or None."""
    try:
        # Try preferred English variants first
        transcript_list = _yt.list(video_id)
        # Find any English transcript (manual or auto-generated)
        transcript = None
        for lang in ["en", "en-AU", "en-US", "en-GB"]:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except Exception:
                pass
        if transcript is None:
            # Fall back to any auto-generated transcript
            try:
                transcript = transcript_list.find_generated_transcript(["en", "en-AU", "en-US"])
            except Exception:
                pass
        if transcript is None:
            return None
        fetched = transcript.fetch()
        return [{"text": s.text, "start": s.start, "duration": s.duration}
                for s in fetched]
    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception:
        return None


def format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def transcript_to_text(entries: list[dict]) -> str:
    return " ".join(e["text"].replace("\n", " ") for e in entries)


def transcript_to_timestamped(entries: list[dict], chunk_secs: int = 120) -> str:
    """Group entries into ~2-minute chunks with timestamps."""
    lines = []
    chunk_text: list[str] = []
    chunk_start = entries[0]["start"] if entries else 0

    for e in entries:
        chunk_text.append(e["text"].replace("\n", " "))
        elapsed = e["start"] - chunk_start
        if elapsed >= chunk_secs:
            ts   = format_timestamp(chunk_start)
            text = " ".join(chunk_text).strip()
            lines.append(f"**[{ts}]** {text}\n")
            chunk_text = []
            chunk_start = e["start"] + e.get("duration", 0)

    if chunk_text:
        ts   = format_timestamp(chunk_start)
        text = " ".join(chunk_text).strip()
        lines.append(f"**[{ts}]** {text}\n")

    return "\n".join(lines)


# ── Claude note generation ────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a university note-taker. Given a video transcript and its context \
(course, week, topic), produce clean structured Markdown study notes. \
Be concise but thorough. Use ## headings, bullet points for key ideas, \
and **bold** for important terms. Preserve any formulas, definitions, or \
step-by-step processes. Do NOT include filler phrases from the transcript \
like "um", "you know", "so basically". Output only the markdown content, \
no preamble."""

def generate_notes(client: anthropic.Anthropic,
                   transcript: str,
                   course: str,
                   week: str,
                   topic: str,
                   video_title: str) -> str:
    prompt = f"""\
Course: {course}
Week: {week} — {topic}
Video title (if known): {video_title}

TRANSCRIPT (first 12000 chars):
{transcript[:12000]}

Generate structured study notes from this transcript.
Include:
1. ## Overview — 2-3 sentence summary
2. ## Key Concepts — bullet list of the main ideas
3. ## Important Terms — **term**: definition for any defined terms
4. ## Key Points — the most exam-relevant takeaways
5. ## Questions to Consider — 2-3 reflection questions
"""
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT,
    )
    return msg.content[0].text.strip()


# ── Vault scanning ────────────────────────────────────────────────────────────

def find_video_links(course_filter: str | None) -> list[dict]:
    """
    Scan canvas_courses markdown files for YouTube links.
    Returns list of {video_id, url, source_file, course_code, week_num, week_topic}
    """
    results = []
    seen_ids: set[str] = set()

    for course_dir in sorted(COURSES.iterdir()):
        if not course_dir.is_dir():
            continue

        # Infer course code from vault folder names
        code = _infer_code(course_dir.name)
        if course_filter and code != course_filter.upper():
            continue

        lec_dir = course_dir / "lectures"
        if not lec_dir.exists():
            continue

        for md in sorted(lec_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="ignore")
            for m in YOUTUBE_RE.finditer(text):
                vid = m.group(1)
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                wn, wt = _week_from_stem(md.stem, code)
                results.append({
                    "video_id":   vid,
                    "url":        f"https://www.youtube.com/watch?v={vid}",
                    "source_file": md,
                    "course_code": code,
                    "course_name": _code_to_name(code),
                    "week_num":   wn,
                    "week_topic": wt,
                    "context_line": _context_line(text, vid),
                })

    return results


def _infer_code(folder_name: str) -> str:
    mapping = {
        "Systems_Analysis_and_Design": "ICT200",
        "Database_Design":             "ICT211",
        "Wireless_Communications":     "ICT220",
        "Object-Oriented_Programming": "ICT221",
    }
    return mapping.get(folder_name, folder_name)


def _code_to_name(code: str) -> str:
    names = {
        "ICT200": "Systems Analysis and Design",
        "ICT211": "Database Design",
        "ICT220": "Wireless Communications",
        "ICT221": "Object-Oriented Programming",
    }
    return names.get(code, code)


WEEK_RE  = re.compile(r'[Ww]eek[_\s]+(\d+)')
MOD_RE   = re.compile(r'[Mm]odule[_\s]+(\d+)')
TOPIC_RE = re.compile(r'\[([^\]]+)\]')


def _week_from_stem(stem: str, code: str) -> tuple[int | None, str]:
    wm = WEEK_RE.search(stem) or MOD_RE.search(stem)
    wn = int(wm.group(1)) if wm else None

    # Derive topic
    bm = TOPIC_RE.search(stem)
    if bm:
        topic = bm.group(1).replace("_", " ").strip()
    else:
        dash = re.search(r'Week_\d+_-_([^_].+?)__', stem)
        if dash:
            topic = re.sub(r'[^\x00-\x7F]', '', dash.group(1)).replace("_", " ").strip()
        else:
            parts = stem.split("__")
            topic = parts[1].replace("_", " ").strip() if len(parts) >= 2 else ""
    return wn, topic


def _context_line(text: str, vid: str) -> str:
    """Return the line that contains the YouTube link for use as a title hint."""
    for line in text.splitlines():
        if vid in line:
            return re.sub(r'\*+|\[|\]|\(.*?\)', '', line).strip()[:80]
    return ""


# ── Week folder resolution ────────────────────────────────────────────────────

def find_week_folder(code: str, week_num: int | None, topic: str) -> Path | None:
    course_dirs = list((VAULT / "Courses").glob(f"{code} — *"))
    if not course_dirs:
        return None
    cdir = course_dirs[0]

    if week_num is None:
        return None

    # Try exact match first, then partial
    for d in cdir.iterdir():
        if not d.is_dir():
            continue
        if d.name.startswith(f"Week {week_num} —"):
            return d

    return None


# ── Output writer ─────────────────────────────────────────────────────────────

def write_video_notes(week_dir: Path, video: dict,
                      notes_md: str, timestamped: str) -> Path:
    out = week_dir / "Video Notes.md"

    # If file exists, append a new section
    if out.exists():
        existing = out.read_text(encoding="utf-8")
        separator = f"\n\n---\n\n## Video: {video['url']}\n\n"
        out.write_text(existing + separator + notes_md + "\n\n### Transcript (timestamped)\n\n" + timestamped,
                       encoding="utf-8")
    else:
        code  = video["course_code"]
        name  = video["course_name"]
        wn    = video["week_num"]
        topic = video["week_topic"]

        header = f"""\
# Week {wn} — Video Notes

**Course:** [[../{code} — {name}|{code} — {name}]]
**Week:** {wn} — {topic}
**Tags:** #{code.lower()} #week{wn} #video #lecture

---

"""
        content = header + notes_md + "\n\n### Transcript (timestamped)\n\n" + timestamped
        out.write_text(content, encoding="utf-8")

    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true", help="List videos without processing")
    parser.add_argument("--course",   help="Filter to one course code, e.g. ICT211")
    parser.add_argument("--limit",    type=int, default=0, help="Max videos to process (0 = all)")
    args = parser.parse_args()

    videos = find_video_links(args.course)
    print(f"Found {len(videos)} unique YouTube videos across courses.\n")

    if args.dry_run:
        for v in videos:
            wdir = find_week_folder(v["course_code"], v["week_num"], v["week_topic"])
            status = "✓ folder found" if wdir else "✗ no folder"
            print(f"  [{v['course_code']} W{v['week_num']}] {v['url']}")
            print(f"      {v['context_line']}")
            print(f"      {status}: {wdir.name if wdir else '—'}\n")
        return

    # Videos that have a matching week folder
    processable = [v for v in videos if find_week_folder(v["course_code"], v["week_num"], v["week_topic"])]
    skipped     = len(videos) - len(processable)
    if skipped:
        print(f"  Skipping {skipped} videos with no matching week folder.\n")

    if args.limit:
        processable = processable[:args.limit]

    client = anthropic.Anthropic()

    ok = 0
    failed = 0
    for i, v in enumerate(processable, 1):
        week_dir = find_week_folder(v["course_code"], v["week_num"], v["week_topic"])
        print(f"[{i}/{len(processable)}] {v['course_code']} W{v['week_num']} — {v['video_id']}")
        print(f"  {v['context_line']}")

        # Fetch transcript
        entries = get_transcript(v["video_id"])
        if not entries:
            print(f"  ✗ No transcript available — skipping.\n")
            failed += 1
            continue

        raw_text   = transcript_to_text(entries)
        timestamped = transcript_to_timestamped(entries)
        print(f"  ✓ Transcript: {len(raw_text)} chars, {len(entries)} segments")

        # Generate notes with Claude
        print(f"  Generating notes with Claude…")
        try:
            notes = generate_notes(
                client,
                raw_text,
                f"{v['course_code']} — {v['course_name']}",
                str(v["week_num"]),
                v["week_topic"],
                v["context_line"],
            )
        except anthropic.APIError as e:
            print(f"  ✗ Claude API error: {e}\n")
            failed += 1
            continue

        out = write_video_notes(week_dir, v, notes, timestamped)
        print(f"  ✓ Saved → {out.relative_to(VAULT)}\n")
        ok += 1
        time.sleep(0.5)   # be gentle with API rate limits

    print(f"\nDone — {ok} videos processed, {failed} skipped (no transcript).")


if __name__ == "__main__":
    main()
