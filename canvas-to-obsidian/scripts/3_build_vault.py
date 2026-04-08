#!/usr/bin/env python3
"""
Build Obsidian university vault — week-based structure.

University/
  Home.md
  _Templates/
  Concepts/
  Courses/
    ICT2XX — Name/
      ICT2XX.md          (course index)
      Week 1 — Topic/
        Lecture Summary.md
        Key Concepts.md
        Flashcards.md
        Study Guide.md
      Week 2 — .../
        ...
      Assignments/
      Exam Prep/
"""

import re
import shutil
from pathlib import Path
from collections import defaultdict

CANVAS = Path.home() / "Desktop" / "canvas_courses"
VAULT  = Path.home() / "Desktop" / "University"

COURSES = [
    {"code": "ICT200", "name": "Systems Analysis and Design", "src": "Systems_Analysis_and_Design"},
    {"code": "ICT211", "name": "Database Design",             "src": "Database_Design"},
    {"code": "ICT220", "name": "Wireless Communications",     "src": "Wireless_Communications"},
    {"code": "ICT221", "name": "Object-Oriented Programming", "src": "Object-Oriented_Programming"},
]

# ── Utilities ─────────────────────────────────────────────────────────────────

def w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")

def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""

def link(target: str, alias: str = "") -> str:
    return f"[[{target}|{alias}]]" if alias else f"[[{target}]]"

def clean_name(s: str) -> str:
    """Remove underscores, emoji, extra whitespace."""
    s = re.sub(r'[^\x00-\x7F]', '', s)   # strip emoji / non-ASCII
    s = s.replace("_", " ").replace("--", "—")
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ── Week / module detection ────────────────────────────────────────────────────

WEEK_RE  = re.compile(r'[Ww]eek[_\s]+(\d+)', re.IGNORECASE)
MOD_RE   = re.compile(r'[Mm]odule[_\s]+(\d+)', re.IGNORECASE)
TOPIC_RE = re.compile(r'\[([^\]]+)\]')          # [Topic Name] in brackets

SKIP_PREFIXES = (
    "Assessment_Information", "Getting_Started", "Workshop_Instructions",
    "Seminar_Recordings", "GETTING_STARTED", "ASSESSMENT_TASKS",
)
ASSIGN_PREFIXES = (
    "Assessment_Information__Task", "ASSESSMENT_TASKS__Assessment_Task",
)


def week_num(stem: str) -> int | None:
    m = WEEK_RE.search(stem) or MOD_RE.search(stem)
    return int(m.group(1)) if m else None


def is_skip(stem: str) -> bool:
    return any(stem.startswith(p) for p in SKIP_PREFIXES)


def is_assignment(stem: str) -> bool:
    return any(stem.startswith(p) for p in ASSIGN_PREFIXES)


def week_topic(stems: list[str], week: int, code: str) -> str:
    """Derive human-readable topic name for a week from its file stems."""
    for stem in stems:
        # ICT220 style: Week_1_[The_World_of_Wireless_Communications]__...
        bm = TOPIC_RE.search(stem)
        if bm:
            return bm.group(1).replace("_", " ").strip()

        # ICT200 style: 📗_Week_1_-_Overview_of_the_SDLC__...
        dash = re.search(r'Week_\d+_-_([^_].+?)__', stem)
        if dash:
            return clean_name(dash.group(1))

        # ICT211/ICT221 style: Module_N__Topic_Name__subsection...
        # Split on __ and take the second part (index 1)
        parts = stem.split("__")
        if len(parts) >= 2 and re.match(r'Module_\d+', parts[0], re.IGNORECASE):
            topic = clean_name(parts[1])
            if topic and not re.match(r'^\d', topic):
                return topic

    return f"Week {week}"


# ── Content extraction ─────────────────────────────────────────────────────────

def extract_bullets(text: str) -> list[str]:
    """Return all bullet-point lines from markdown."""
    return [
        l.lstrip("-* ").strip()
        for l in text.splitlines()
        if re.match(r'^\s*[-*]\s+\S', l)
    ]

def extract_bold_terms(text: str) -> list[str]:
    """Return words/phrases wrapped in **...**."""
    return list(dict.fromkeys(
        m.strip() for m in re.findall(r'\*\*([^*\n]{2,60})\*\*', text)
        if not m.strip().startswith(("Q:", "A:"))
    ))

def extract_headings(text: str) -> list[tuple[int, str]]:
    """Return list of (level, text) for all headings."""
    results = []
    for line in text.splitlines():
        m = re.match(r'^(#{1,4})\s+(.+)', line)
        if m:
            results.append((len(m.group(1)), m.group(2).strip()))
    return results

def extract_numbered_items(text: str) -> list[str]:
    return [
        re.sub(r'^\d+\.\s+', '', l).strip()
        for l in text.splitlines()
        if re.match(r'^\d+\.\s+\S', l)
    ]

def first_paragraph(text: str) -> str:
    """Return first non-heading, non-empty paragraph (≤300 chars)."""
    lines = text.splitlines()
    para = []
    in_para = False
    for line in lines:
        if line.startswith("#") or line.startswith("---"):
            if in_para:
                break
            continue
        if line.strip():
            para.append(line.strip())
            in_para = True
        elif in_para:
            break
    result = " ".join(para)
    return result[:300] + ("…" if len(result) > 300 else "")


# ── Weekly file generators ─────────────────────────────────────────────────────

def make_lecture_summary(week: int, topic: str, code: str, name: str,
                         files: list[Path]) -> str:
    parts = [
        f"# Week {week} — Lecture Summary",
        f"",
        f"**Course:** {link(f'../{code} — {name}', f'{code} — {name}')}  ",
        f"**Week:** {week} — {topic}  ",
        f"**Tags:** #{code.lower()} #week{week} #lecture",
        "",
        "---",
        "",
    ]

    for f in files:
        text = read(f)
        title_m = re.match(r'^#\s+(.+)', text, re.MULTILINE)
        title   = title_m.group(1).strip() if title_m else clean_name(f.stem)

        # Strip the H1 and re-level all headings down by one
        body = re.sub(r'^# .+\n', '', text, count=1)
        body = re.sub(r'^(#{1,4})', lambda m: '#' + m.group(1), body, flags=re.MULTILINE)
        body = re.sub(r'\n{3,}', '\n\n', body).strip()

        parts += [f"## {title}", "", body, "", "---", ""]

    return "\n".join(parts)


def make_key_concepts(week: int, topic: str, code: str, name: str,
                      files: list[Path]) -> str:
    all_bullets: list[str] = []
    all_terms:   list[str] = []
    headings:    list[str] = []

    for f in files:
        text = read(f)
        all_bullets += extract_bullets(text)
        all_terms   += extract_bold_terms(text)
        for lvl, h in extract_headings(text):
            if lvl >= 2:
                headings.append(h)

    # Deduplicate
    all_bullets = list(dict.fromkeys(b for b in all_bullets if len(b) > 10))
    all_terms   = list(dict.fromkeys(t for t in all_terms if 3 < len(t) < 80))[:20]

    bullet_block = "\n".join(f"- {b}" for b in all_bullets[:30]) or "- *(to be filled)*"

    term_rows = "\n".join(f"| **{t}** | |" for t in all_terms) if all_terms \
        else "| | |"

    toc = "\n".join(f"- {h}" for h in headings[:15]) or "- *(see lecture summary)*"

    return f"""\
# Week {week} — Key Concepts

**Course:** {link(f"../{code} — {name}", f"{code} — {name}")}
**Week:** {week} — {topic}
**Tags:** #{code.lower()} #week{week} #concepts

---

## Topics Covered This Week

{toc}

---

## Core Ideas

{bullet_block}

---

## Key Terms

| Term | Definition |
|------|------------|
{term_rows}

---

## Links

- {link("Lecture Summary", "Lecture Summary")}
- {link("Flashcards", "Flashcards")}
- {link("Study Guide", "Study Guide")}
"""


def make_flashcards(week: int, topic: str, code: str, name: str,
                    files: list[Path]) -> str:
    cards: list[tuple[str, str]] = []

    for f in files:
        text = read(f)

        # Learning outcomes → cards
        lo_block = re.search(
            r'(?:Learning [Oo]utcome|On successful completion)[^\n]*\n+((?:[-\d].*\n?)+)',
            text
        )
        if lo_block:
            for item in re.findall(r'[-\d]+[\.\)]\s+(.+)', lo_block.group(1)):
                q = re.sub(r'^(Explain|Describe|Define|Outline|List|Discuss|Identify)\s+', '', item).strip()
                cards.append((f"Explain: {q}", ""))

        # Bold term definitions
        for m in re.finditer(r'\*\*([^*\n]{3,50})\*\*\s+(?:is|are|refers to|means)\s+([^.\n]{10,150})', text):
            cards.append((f"What is *{m.group(1)}*?", m.group(2).strip() + "."))

        # Numbered concept items with ≤ 10 words → definition cards
        for item in extract_numbered_items(text):
            if 3 < len(item.split()) <= 12:
                cards.append((f"Define: {item}", ""))

    if not cards:
        cards = [
            (f"What are the main topics covered in Week {week} ({topic})?", ""),
            (f"What is the significance of {topic}?", ""),
        ]

    # Deduplicate questions
    seen: set[str] = set()
    unique_cards: list[tuple[str, str]] = []
    for q, a in cards:
        if q not in seen:
            seen.add(q)
            unique_cards.append((q, a))

    card_blocks = []
    for q, a in unique_cards[:20]:
        answer = a if a else "*(fill in)*"
        card_blocks.append(f"#flashcard\n\n**Q:** {q}\n**A:** {answer}")

    cards_md = "\n\n---\n\n".join(card_blocks)

    return f"""\
# Week {week} — Flashcards

**Course:** {link(f"../{code} — {name}", f"{code} — {name}")}
**Week:** {week} — {topic}
**Tags:** #{code.lower()} #week{week} #flashcard

---

{cards_md}

---

> {link("Key Concepts", "← Key Concepts")}  ·  {link("Study Guide", "Study Guide →")}
"""


def make_study_guide(week: int, topic: str, code: str, name: str,
                     files: list[Path]) -> str:
    # Learning outcomes from files
    outcomes: list[str] = []
    for f in files:
        text = read(f)
        lo_m = re.search(
            r'(?:Learning [Oo]utcome|On successful completion)[^\n]*\n+((?:[-\d\*].*\n?)+)',
            text
        )
        if lo_m:
            for item in re.findall(r'[-\d\*]+[\.\)]\s+(.+)', lo_m.group(1)):
                outcomes.append(item.strip())
    if not outcomes:
        outcomes = ["*(Review the lecture summary for this week's outcomes)*"]

    outcome_checks = "\n".join(f"- [ ] {o}" for o in outcomes[:10])

    # File links
    file_links = "\n".join(
        f"- {link(f.stem, clean_name(f.stem.split('__')[-1]) if '__' in f.stem else clean_name(f.stem))}"
        for f in files
    )

    # Summary of first paragraph from each file
    summaries = []
    for f in files:
        text = read(f)
        title_m = re.match(r'^#\s+(.+)', text, re.MULTILINE)
        title = title_m.group(1) if title_m else clean_name(f.stem)
        para  = first_paragraph(text)
        if para:
            summaries.append(f"**{title}:** {para}")
    summary_block = "\n\n".join(summaries[:4]) or "*(see lecture files)*"

    return f"""\
# Week {week} — Study Guide

**Course:** {link(f"../{code} — {name}", f"{code} — {name}")}
**Week:** {week} — {topic}
**Tags:** #{code.lower()} #week{week} #studyguide

---

## Learning Outcomes

{outcome_checks}

---

## Week Overview

{summary_block}

---

## Lecture Files This Week

{file_links}

---

## Study Checklist

- [ ] Read {link("Lecture Summary")}
- [ ] Review {link("Key Concepts")}
- [ ] Complete {link("Flashcards")}
- [ ] Fill any gaps in Key Terms table
- [ ] Review related {link(f"../../Concepts/", "Concepts")}

---

## Practice Questions

1.
2.
3.

---

## Notes / Questions for Lecturer

-

---

## Related Weeks

- {link(f"../Week {week - 1} —" if week > 1 else "../", f"← Week {week - 1}" if week > 1 else "Course Home")}
- {link(f"../", "Course Index")}
"""


# ── Assignment file ────────────────────────────────────────────────────────────

def make_assignment_index(code: str, name: str, files: list[Path]) -> str:
    rows = []
    for f in files:
        text = read(f)
        # Try to find deadline
        due = ""
        dm  = re.search(r'(?:\*\*Due[^*]*\*\*|Due:)[^\n]*', text, re.IGNORECASE)
        if dm:
            due = re.sub(r'\*+', '', dm.group()).strip()[:80]
        title_m = re.match(r'^#\s+(.+)', text, re.MULTILINE)
        title   = title_m.group(1) if title_m else clean_name(f.stem)
        rows.append(f"| {link(f.stem, title)} | {due} | [ ] |")

    table = "\n".join(rows) or "| — | — | — |"

    return f"""\
# Assignments — {code}

**Course:** {link(f"../{code} — {name}", name)}
**Tags:** #{code.lower()} #assignment

---

| Assignment | Due | Done |
|-----------|-----|------|
{table}
"""


# ── Exam Prep ─────────────────────────────────────────────────────────────────

def make_exam_prep(code: str, name: str, weeks: list[tuple[int, str]]) -> str:
    checklist = "\n".join(
        f"- [ ] Week {n} — {link(f'../Week {n} — {t}/Study Guide', t)}"
        for n, t in weeks
    )
    topic_table = "\n".join(
        f"| {link(f'../Week {n} — {t}/Key Concepts', t)} | | 🔴 |"
        for n, t in weeks
    )

    return f"""\
# Exam Prep — {code}

**Course:** {link(f"../{code} — {name}", name)}
**Tags:** #{code.lower()} #exam

---

## Syllabus Coverage

{checklist}

---

## Confidence Tracker

| Topic | Notes | Confidence |
|-------|-------|------------|
{topic_table}

---

## High-Priority Flashcards

{chr(10).join(link(f"../Week {n} — {t}/Flashcards", f"Week {n} Flashcards") for n, t in weeks[:6])}

---

## Practice Questions

1.
2.
3.

---

## Weak Areas

- [ ]

## Exam Day Checklist

- [ ] Review all flashcards
- [ ] Re-read key concepts for weak areas
- [ ] Complete practice questions
"""


# ── Course index ──────────────────────────────────────────────────────────────

def make_course_index(code: str, name: str, weeks: list[tuple[int, str]]) -> str:
    week_links = "\n".join(
        f"- {link(f'Week {n} — {t}/Study Guide', f'Week {n} — {t}')}"
        for n, t in weeks
    )

    return f"""\
# {code} — {name}

**Trimester:** Tri1 2026
**Tags:** #{code.lower()} #university

---

## Weekly Notes

{week_links}

---

## Quick Access

| | |
|--|--|
| {link("Assignments/", "Assignments")} | {link("Exam Prep/Exam Prep — " + code, "Exam Prep")} |

---

## Back

{link("../../Home", "Home")}
"""


# ── Concepts folder ───────────────────────────────────────────────────────────

SHARED_CONCEPTS = [
    ("OOP Principles", ["Encapsulation", "Inheritance", "Polymorphism", "Abstraction"],
     ["ICT221", "ICT200"]),
    ("Relational Model", ["Tables", "Primary Keys", "Foreign Keys", "Normalisation"],
     ["ICT211"]),
    ("System Design", ["SDLC", "Use Cases", "Class Diagrams", "Architecture"],
     ["ICT200"]),
    ("Wireless Fundamentals", ["RF Spectrum", "Modulation", "OFDM", "MIMO"],
     ["ICT220"]),
]

def make_concepts() -> None:
    cdir = VAULT / "Concepts"
    for concept_name, subtopics, courses in SHARED_CONCEPTS:
        course_links = "  ".join(link(f"../Courses/{c} — */", c) for c in courses)
        subtopic_list = "\n".join(f"- {s}" for s in subtopics)
        content = f"""\
# {concept_name}

**Related Courses:** {course_links}
**Tags:** #concept #{concept_name.lower().replace(" ", "-")}

---

## Overview

> *(Add a summary here)*

## Key Ideas

{subtopic_list}

## Notes

## Related Concepts

"""
        w(cdir / f"{concept_name}.md", content)


# ── Home ──────────────────────────────────────────────────────────────────────

def make_home() -> None:
    def _clink(c: dict) -> str:
        target = "Courses/" + c["code"] + " — " + c["name"] + "/" + c["code"] + " — " + c["name"]
        alias  = c["code"] + " — " + c["name"]
        return "- " + link(target, alias)
    course_links = "\n".join(_clink(c) for c in COURSES)
    content = f"""\
# University Vault

> **Trimester:** Tri1 2026  |  **Student:** Shreeshail Nepal

---

## Courses

{course_links}

---

## Concepts

{link("Concepts/", "Browse All Concepts")}

---

## Tags

`#lecture` · `#concepts` · `#flashcard` · `#studyguide` · `#assignment` · `#exam`
"""
    w(VAULT / "Home.md", content)


# ── Templates ─────────────────────────────────────────────────────────────────

def make_templates() -> None:
    t = VAULT / "_Templates"

    w(t / "Lecture Summary.md", """\
# Week {{week}} — Lecture Summary

**Course:** [[../COURSE|COURSE]]
**Week:** {{week}} — {{topic}}
**Tags:** #course #week{{week}} #lecture

---

## {{Lecture Title}}

*(paste or write lecture notes here)*

---
""")

    w(t / "Key Concepts.md", """\
# Week {{week}} — Key Concepts

**Course:** [[../COURSE|COURSE]]
**Tags:** #course #week{{week}} #concepts

---

## Core Ideas

-

## Key Terms

| Term | Definition |
|------|------------|
|      |            |
""")

    w(t / "Flashcards.md", """\
# Week {{week}} — Flashcards

**Course:** [[../COURSE|COURSE]]
**Tags:** #course #week{{week}} #flashcard

---

#flashcard

**Q:**
**A:**

---
""")

    w(t / "Study Guide.md", """\
# Week {{week}} — Study Guide

**Course:** [[../COURSE|COURSE]]
**Tags:** #course #week{{week}} #studyguide

---

## Learning Outcomes

- [ ]

## Checklist

- [ ] [[Lecture Summary]]
- [ ] [[Key Concepts]]
- [ ] [[Flashcards]]

## Practice Questions

1.
""")


# ── Obsidian config ───────────────────────────────────────────────────────────

def make_obsidian_config() -> None:
    cfg = VAULT / ".obsidian"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "app.json").write_text('{"legacyEditor":false,"foldHeading":true,"showLineNumber":true}')
    (cfg / "community-plugins.json").write_text('["dataview","obsidian-spaced-repetition"]')


# ── Main ──────────────────────────────────────────────────────────────────────

def build_course(course: dict) -> None:
    code    = course["code"]
    name    = course["name"]
    src_dir = CANVAS / course["src"] / "lectures"
    cdir    = VAULT / "Courses" / f"{code} — {name}"

    # Group lecture files by week number
    week_files: dict[int, list[Path]] = defaultdict(list)
    assign_files: list[Path] = []

    for f in sorted(src_dir.glob("*.md")):
        stem = f.stem
        if is_assignment(stem):
            assign_files.append(f)
            continue
        if is_skip(stem):
            continue
        wn = week_num(stem)
        if wn:
            week_files[wn].append(f)

    # Build week list (sorted)
    weeks_sorted = sorted(week_files.items())
    week_meta: list[tuple[int, str]] = []

    for wn, files in weeks_sorted:
        stems = [f.stem for f in files]
        topic = week_topic(stems, wn, code)
        week_meta.append((wn, topic))

        wdir = cdir / f"Week {wn} — {topic}"

        w(wdir / "Lecture Summary.md",
          make_lecture_summary(wn, topic, code, name, files))
        w(wdir / "Key Concepts.md",
          make_key_concepts(wn, topic, code, name, files))
        w(wdir / "Flashcards.md",
          make_flashcards(wn, topic, code, name, files))
        w(wdir / "Study Guide.md",
          make_study_guide(wn, topic, code, name, files))

    # Assignments
    adir = cdir / "Assignments"
    adir.mkdir(parents=True, exist_ok=True)
    for f in assign_files:
        shutil.copy2(f, adir / f.name)
    w(adir / "_Assignments Index.md",
      make_assignment_index(code, name, assign_files))

    # Exam Prep
    w(cdir / "Exam Prep" / f"Exam Prep — {code}.md",
      make_exam_prep(code, name, week_meta))

    # Course index
    w(cdir / f"{code} — {name}.md",
      make_course_index(code, name, week_meta))

    print(f"  {code}: {len(week_meta)} weeks, {len(assign_files)} assignments")


def main() -> None:
    if VAULT.exists():
        shutil.rmtree(VAULT)
    VAULT.mkdir()
    print(f"Building vault → {VAULT}\n")

    make_obsidian_config()
    make_home()
    make_templates()
    make_concepts()

    for course in COURSES:
        build_course(course)

    total = len(list(VAULT.rglob("*.md")))
    print(f"\nDone — {total} files in vault.")


if __name__ == "__main__":
    main()
