# Canvas → Obsidian

A pipeline of five Python scripts that download your Canvas LMS course materials and build a fully-linked, week-organised Obsidian vault — with YouTube video notes and slide conversion included.

---

## What it produces

```
University/
└── Courses/
    └── ICT211 — Database Design/
        ├── Week 1 — Introducing Databases/
        │   ├── Lecture Summary.md   ← real Canvas content
        │   ├── Key Concepts.md      ← extracted bullets + terms table
        │   ├── Flashcards.md        ← auto Q&A with #flashcard tags
        │   ├── Study Guide.md       ← learning outcomes checklist
        │   ├── Video Notes.md       ← from YouTube transcripts (script 4)
        │   └── Slide Notes.md       ← from PDF/PPTX slides (script 5)
        ├── Assignments/
        └── Exam Prep/
```

See [`examples/vault-structure/example-vault-tree.md`](examples/vault-structure/example-vault-tree.md) for the full tree.

---

## Requirements

- Python 3.11+
- An Obsidian installation (free) — [obsidian.md](https://obsidian.md)
- A Canvas LMS account with API access
- An Anthropic API key (scripts 4 and 5 only) — [console.anthropic.com](https://console.anthropic.com)
- LibreOffice (script 5, PPTX only) — `brew install --cask libreoffice`

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Before running any script, open it and update the **three variables** at the top:

| Variable | Where | Example |
|----------|-------|---------|
| `CANVAS_URL` | scripts 1–3 | `https://youruni.instructure.com` |
| `CANVAS_TOKEN` | script 1 | see below |
| `COURSES` list | scripts 2–5 | your course codes + names |

### Getting your Canvas API token

1. Log into Canvas
2. Go to **Account → Settings → Approved Integrations**
3. Click **+ New Access Token**
4. Copy the token — you only see it once

### Setting your Anthropic API key (scripts 4 & 5)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Add that line to your `~/.zshrc` or `~/.bashrc` to persist it.

---

## The Pipeline

Run the scripts in order. Each one builds on the output of the previous.

```
Canvas LMS
    │
    ▼
[1] download_canvas.py   →   canvas_courses/
    │
    ▼
[2] clean_markdown.py    →   canvas_courses/  (cleaned in-place)
    │
    ▼
[3] build_vault.py       →   University/  (Obsidian vault)
    │
    ├──▶ [4] transcribe_videos.py  →  Video Notes.md per week
    │
    └──▶ [5] convert_slides.py     →  Slide Notes.md per week
```

---

## Script 1 — Download Canvas (`scripts/1_download_canvas.py`)

Downloads all course materials from Canvas via the REST API and saves them as markdown files.

### What it downloads
- Module pages (lecture notes, readings, links)
- Assignments (descriptions, due dates, rubrics)
- Announcements
- Discussion topics and replies

> **Note:** Canvas file attachments (PDFs, PPTXs) require staff-level API permissions. If you get a `403` error on files, download them manually through the browser — that's what script 5 handles.

### Usage

```bash
# Download all active courses
python3 scripts/1_download_canvas.py \
  --url https://youruni.instructure.com \
  --token YOUR_TOKEN

# Download a single course by ID
python3 scripts/1_download_canvas.py \
  --url https://youruni.instructure.com \
  --token YOUR_TOKEN \
  --course-id 12345

# Specify output folder (default: ./canvas_courses)
python3 scripts/1_download_canvas.py \
  --url https://youruni.instructure.com \
  --token YOUR_TOKEN \
  --output ~/Downloads/my_canvas
```

### Finding your course ID

The course ID is in the URL when you open a course:
`https://youruni.instructure.com/courses/`**`12345`**

### Output structure

```
canvas_courses/
└── Database_Design/
    ├── lectures/      ← module pages
    ├── assignments/   ← assignment descriptions
    ├── announcements/
    └── discussions/
```

---

## Script 2 — Clean Markdown (`scripts/2_clean_markdown.py`)

Cleans and restructures the raw markdown files downloaded by script 1.

### What it does
- Removes broken Canvas image links (inaccessible without auth)
- Replaces Canvas file download links with `filename *(Canvas file)*`
- Converts numbered concept lists to bullet points
- Promotes standalone bold lines to `###` headings
- For assignment files: extracts a `## Requirements` section and a `## Deadlines` section
- Strips AI-policy and academic integrity boilerplate (same text in every file)

### Usage

```bash
# Cleans all files in canvas_courses/ in-place
python3 scripts/2_clean_markdown.py
```

No arguments needed — it finds `canvas_courses/` relative to `~/Desktop` automatically. Edit the `CANVAS` path variable at the top if your folder is elsewhere.

---

## Script 3 — Build Vault (`scripts/3_build_vault.py`)

Organises the cleaned markdown into a week-based Obsidian vault and generates the four study files for each week.

### What it creates per week folder

| File | Contents |
|------|----------|
| `Lecture Summary.md` | All lecture content for the week combined under `##` headings |
| `Key Concepts.md` | Extracted bullet points, topic list, key terms table |
| `Flashcards.md` | Auto-generated Q&A cards tagged `#flashcard` for Spaced Repetition |
| `Study Guide.md` | Learning outcomes checklist, week overview, practice questions |

It also generates:
- A **course index** (`ICT211 — Database Design.md`) with links to every week
- **Assignments/** folder with an index table
- **Exam Prep/** with a confidence tracker and syllabus checklist
- **`_Templates/`** with blank templates for new notes
- **`Concepts/`** for cross-course atomic notes

### Customising for your courses

Edit the `COURSES` list near the top of the script:

```python
COURSES = [
    {"code": "ICT200", "name": "Systems Analysis and Design", "src": "Systems_Analysis_and_Design"},
    {"code": "ICT211", "name": "Database Design",             "src": "Database_Design"},
    # add your courses here — "src" must match the canvas_courses/ subfolder name
]
```

### Usage

```bash
python3 scripts/3_build_vault.py
```

Output: `~/Desktop/University/`

### Opening in Obsidian

1. Open Obsidian
2. Click **Open folder as vault**
3. Select `~/Desktop/University`
4. Install the **Dataview** and **Obsidian Spaced Repetition** plugins (community plugins)

---

## Script 4 — Transcribe Videos (`scripts/4_transcribe_videos.py`)

Finds every YouTube link in your Canvas lecture files, fetches the caption track, sends it to Claude, and writes a `Video Notes.md` into the matching week folder.

### Requirements
- Anthropic API key (set `ANTHROPIC_API_KEY` environment variable)
- Videos must have captions enabled on YouTube (most educational videos do)

### What it produces per video

```markdown
# Week 2 — Video Notes

## Overview
Two-to-three sentence summary of the video content.

## Key Concepts
- Bullet list of main ideas

## Important Terms
**term**: definition

## Key Points
Exam-relevant takeaways

## Questions to Consider
Reflection prompts

### Transcript (timestamped)
**[0:00]** First two minutes of transcript...
**[2:00]** Next chunk...
```

### Usage

```bash
# Preview what will be processed (no API calls)
python3 scripts/4_transcribe_videos.py --dry-run

# Process all videos across all courses
python3 scripts/4_transcribe_videos.py

# One course only
python3 scripts/4_transcribe_videos.py --course ICT200

# Limit number of videos (useful for testing)
python3 scripts/4_transcribe_videos.py --limit 5
```

### Cost estimate

Each video uses roughly 1,000–3,000 Claude output tokens. At claude-opus-4-6 pricing (~$15/M output tokens), processing all 36 videos costs approximately **$0.50–$1.50 total**.

---

## Script 5 — Convert Slides (`scripts/5_convert_slides.py`)

Converts downloaded PDF or PPTX slide files into structured study notes using `pymupdf4llm` for text extraction and Claude for restructuring.

### Requirements
- Anthropic API key
- For PPTX/PPT files: LibreOffice (`brew install --cask libreoffice`)
- Slides downloaded manually from Canvas

### Downloading slides from Canvas

Because the Canvas API blocks file downloads for most student accounts:

1. Log into Canvas in your browser
2. Navigate to each course → **Files** (or the lecture page with "Downloadable slides")
3. Download the PDFs/PPTXs
4. Sort them into subfolders by course code:

```
~/Desktop/slides/
├── ICT200/
│   ├── Week1_SDLC.pdf
│   └── Week2_Requirements.pptx
├── ICT211/
│   ├── Module1_Intro.pdf
│   └── Module2_ERD.pdf
└── ICT220/
    └── Week3_RF.pdf
```

The script detects the week number from the filename — include `Week1`, `Week_1`, `Module1`, etc. in the filename for automatic matching.

### Usage

```bash
# Preview matches without processing
python3 scripts/5_convert_slides.py --dry-run

# Process all slides
python3 scripts/5_convert_slides.py

# One course only
python3 scripts/5_convert_slides.py --course ICT211

# Custom slides folder
python3 scripts/5_convert_slides.py --slides-dir ~/Downloads/my_slides
```

### What it produces per slide file

```markdown
# Week 3 — Slide Notes

## Overview
What this lecture covers.

## Key Concepts
- One bullet per slide/section

## Important Terms
**term**: definition

## Diagrams / Figures
Description of key diagrams.

## Key Takeaways
3–5 exam-relevant points.
```

Files saved into the matching week folder as `Slide Notes.md`. A raw extraction `_raw_filename.md` is also saved so you can verify accuracy.

> **Image-based PDFs:** If your slides were scanned or saved as images, `pymupdf4llm` cannot extract text. Export them from PowerPoint as "PDF (text-based)" or use an OCR tool first.

---

## Recommended Obsidian Plugins

| Plugin | Purpose | Install |
|--------|---------|---------|
| **Dataview** | Query notes like a database (e.g. list all #exam notes) | Community plugins |
| **Obsidian Spaced Repetition** | Use the `#flashcard` tags in Flashcards.md for active recall | Community plugins |
| **Templater** | Use the `_Templates/` folder to create new notes from templates | Community plugins |
| **Calendar** | Week-by-week navigation view | Community plugins |

---

## Troubleshooting

### `403 Forbidden` on Canvas files
Your API token doesn't have file-access permissions. Download slides manually and use script 5.

### `No transcript available` for a video
The video has captions disabled. Options:
- Use `yt-dlp` to download the video and run OpenAI Whisper locally:
  ```bash
  pip install yt-dlp openai-whisper
  yt-dlp -x --audio-format mp3 "https://youtube.com/watch?v=VIDEO_ID" -o video.mp3
  whisper video.mp3 --language en
  ```

### `LibreOffice not found` for PPTX conversion
```bash
brew install --cask libreoffice
```
Or export your PPTX to PDF manually in PowerPoint/Keynote before running script 5.

### Claude API authentication error
Make sure the environment variable is set in the same terminal session:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 scripts/4_transcribe_videos.py
```

### Week folder not found for a video/slide
Run with `--dry-run` to see which files can't be matched. Then either:
- Rename the file to include `Week1`, `Week_1`, or `Module1` in the filename
- Manually move the generated note from `_Unmatched/` to the correct week folder

---

## Project Structure

```
canvas-to-obsidian/
├── README.md
├── requirements.txt
├── scripts/
│   ├── 1_download_canvas.py     ← Canvas API downloader
│   ├── 2_clean_markdown.py      ← Markdown cleaner + formatter
│   ├── 3_build_vault.py         ← Obsidian vault generator
│   ├── 4_transcribe_videos.py   ← YouTube transcript → notes
│   └── 5_convert_slides.py      ← PDF/PPTX slides → notes
└── examples/
    └── vault-structure/
        └── example-vault-tree.md
```

---

## License

MIT — use freely, modify as needed.
