#!/usr/bin/env python3
"""
Convert Canvas-downloaded markdown files into clean, structured markdown.
Rules:
 - Headings for lecture sections
 - Bullet points for key ideas
 - Code blocks preserved
 - Assignments separated into Requirements and Deadlines
"""

import re
import sys
from pathlib import Path

CANVAS_URL = "https://learn.usc.edu.au"

# ── helpers ──────────────────────────────────────────────────────────────────

def remove_canvas_images(text: str) -> str:
    """Remove embedded Canvas image links (inaccessible without auth)."""
    # ![alt](https://learn.usc.edu.au/.../preview?verifier=...)
    text = re.sub(r'!\[[^\]]*\]\(https://learn\.usc\.edu\.au[^)]+\)', '', text)
    return text

def clean_canvas_file_links(text: str) -> str:
    """Replace Canvas file download links with just the link text (no extra bold)."""
    def replace_link(m: re.Match) -> str:
        link_text = m.group(1).strip('*').strip()
        return f'{link_text} *(Canvas file)*'
    text = re.sub(
        r'\[([^\]]+)\]\(https://learn\.usc\.edu\.au/courses/[^)]+\)',
        replace_link,
        text
    )
    return text

def fix_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive blank lines to 2."""
    return re.sub(r'\n{4,}', '\n\n\n', text)

def strip_trailing_whitespace(text: str) -> str:
    lines = [l.rstrip() for l in text.splitlines()]
    return '\n'.join(lines)

def ensure_newline_end(text: str) -> str:
    return text.rstrip('\n') + '\n'

def bullets_for_numbered_concepts(text: str) -> str:
    """
    Convert standalone numbered lists that are clearly concept enumerations
    (short lines, not instructions) into bullet lists.
    Heuristic: numbered list items ≤ 120 chars that don't start with an
    imperative verb (Install, Read, Watch, Download, Complete, Submit, Go).
    """
    imperative = re.compile(
        r'^\d+\.\s+(Install|Read|Watch|Download|Complete|Submit|Go|Click|Open|'
        r'Access|Log|Sign|Navigate|Visit|Check|Fill|Upload|Review)\b',
        re.IGNORECASE
    )

    def replace_list(m: re.Match) -> str:
        full = m.group(0)
        lines = full.splitlines()
        converted = []
        all_short = all(len(l) <= 140 for l in lines)
        any_imperative = any(imperative.match(l) for l in lines)
        if all_short and not any_imperative:
            for l in lines:
                converted.append(re.sub(r'^\d+\.\s+', '- ', l))
            return '\n'.join(converted)
        return full

    # Match blocks of consecutive numbered lines
    pattern = re.compile(r'(?m)(^\d+\. .+\n?)+')
    return pattern.sub(replace_list, text)


# ── assignment-specific processing ───────────────────────────────────────────

DATE_PATTERNS = [
    # **Label:** value  (bold label, value outside bold — common Canvas format)
    r'\*\*(?:Due|Available From|Available To|Deadline|Due Date|Submitted|Submit by):\*\*[^\n]+',
    # **Label: value**  (everything bold)
    r'\*\*(?:Due|Available From|Available To|Deadline|Due Date|Submitted|Submit by)[:\s*]+[^*\n]+\*\*',
    # Plain: Label: value
    r'(?:Due|Available From|Available To|Deadline|Due Date):\s+[^\n]+',
    r'The completed assignment is to be submitted on or before[^\n]+',
]
DATE_RE = re.compile('|'.join(DATE_PATTERNS), re.IGNORECASE)

DEADLINE_SECTION_HEADERS = re.compile(
    r'^#+\s*(deadline|due date|submission|available from|available to|dates)',
    re.IGNORECASE | re.MULTILINE
)

def extract_deadlines(text: str) -> tuple[str, list[str]]:
    """Return (text_without_deadlines, list_of_deadline_lines)."""
    deadlines = []
    remaining_lines = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if DATE_RE.search(line):
            deadlines.append(line.strip())
            i += 1
        else:
            remaining_lines.append(line)
            i += 1
    return '\n'.join(remaining_lines), deadlines


def format_assignment(text: str, title: str) -> str:
    """Restructure an assignment file into Requirements + Deadlines."""

    # Pull out raw deadline lines
    body, deadline_lines = extract_deadlines(text)

    # Remove the original H1 title (we'll re-add it cleanly)
    body = re.sub(r'^#\s+.+\n?', '', body, count=1)

    # Remove AI-policy boilerplate (verbose, same across all assignments)
    ai_policy_start = re.compile(
        r'#+\s*AI-Supported Learning Statement.*?(?=\n#[^#]|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    body = ai_policy_start.sub('', body)

    # Remove Academic Integrity boilerplate
    integrity_start = re.compile(
        r'#+\s*Academic Integrity.*?(?=\n#[^#]|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    body = integrity_start.sub('', body)

    # Tidy remaining body
    body = bullets_for_numbered_concepts(body)
    body = fix_blank_lines(body).strip()

    # Build clean output
    out = [f'# {title}\n']

    # ── Requirements section ──────────────────────────────────────────────
    out.append('## Requirements\n')
    # Extract key details: marks, length, structure lines
    detail_lines = []
    content_lines = []
    detail_re = re.compile(
        r'^\*\*(Marks|Length|Structure|Format|Weight|Worth)[:\*]',
        re.IGNORECASE
    )
    for line in body.splitlines():
        if detail_re.match(line):
            detail_lines.append(f'- {line.strip()}')
        else:
            content_lines.append(line)

    if detail_lines:
        out.append('\n'.join(detail_lines) + '\n')

    # Add task instructions content
    content_body = '\n'.join(content_lines).strip()
    # Upgrade ### sub-headings to ## inside requirements
    content_body = re.sub(r'^### ', '### ', content_body, flags=re.MULTILINE)
    if content_body:
        out.append(content_body + '\n')

    # ── Deadlines section ─────────────────────────────────────────────────
    if deadline_lines:
        out.append('\n## Deadlines\n')
        seen = set()
        for dl in deadline_lines:
            clean = dl.strip('- ').strip()
            if clean and clean not in seen:
                out.append(f'- {clean}')
                seen.add(clean)
        out.append('')

    return '\n'.join(out)


# ── lecture processing ────────────────────────────────────────────────────────

def format_lecture(text: str) -> str:
    """Clean up a lecture/module page."""
    text = bullets_for_numbered_concepts(text)

    # Promote orphan bold lines that look like section headings
    # e.g.  **Key Concepts:**  →  ### Key Concepts
    def bold_to_heading(m: re.Match) -> str:
        inner = m.group(1).rstrip(':').strip()
        return f'### {inner}'

    text = re.sub(
        r'^(?!#+)\*\*([A-Z][^*\n]{3,50})\*\*\s*:?\s*$',
        bold_to_heading,
        text,
        flags=re.MULTILINE
    )

    return text


# ── per-file dispatch ─────────────────────────────────────────────────────────

ASSIGNMENT_PATH_RE = re.compile(r'/(assignments|Assessment_Task|Task_\d)', re.IGNORECASE)
ASSIGNMENT_NAME_RE = re.compile(
    r'(assessment|task_\d|assignment_\d)',
    re.IGNORECASE
)

def is_assignment_file(path: Path) -> bool:
    if 'assignments' in path.parts:
        return True
    name = path.stem.lower()
    return bool(re.search(r'(assessment_task|task_\d|task_information)', name))


def process_file(path: Path) -> None:
    original = path.read_text(encoding='utf-8')
    text = original

    # Universal cleanup
    text = remove_canvas_images(text)
    text = clean_canvas_file_links(text)
    text = strip_trailing_whitespace(text)

    # Extract title from first H1
    title_match = re.match(r'^#\s+(.+)', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.replace('_', ' ')

    if is_assignment_file(path):
        text = format_assignment(text, title)
    else:
        text = format_lecture(text)
        text = fix_blank_lines(text)

    text = ensure_newline_end(text)

    if text != original:
        path.write_text(text, encoding='utf-8')
        print(f'  updated: {path.relative_to(Path.home() / "Desktop")}')
    else:
        print(f'  unchanged: {path.relative_to(Path.home() / "Desktop")}')


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    root = Path.home() / 'Desktop' / 'canvas_courses'
    if not root.exists():
        print(f'Error: {root} not found', file=sys.stderr)
        sys.exit(1)

    files = sorted(root.rglob('*.md'))
    print(f'Processing {len(files)} files in {root}\n')

    updated = 0
    for f in files:
        before = f.read_text(encoding='utf-8')
        process_file(f)
        after = f.read_text(encoding='utf-8')
        if before != after:
            updated += 1

    print(f'\nDone — {updated}/{len(files)} files updated.')


if __name__ == '__main__':
    main()
