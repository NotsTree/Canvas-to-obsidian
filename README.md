# Canvas → Obsidian

## Description

A pipeline of five Python scripts that automatically downloads course materials from Canvas LMS and transforms them into a fully-linked, week-organised Obsidian vault. Includes automatic YouTube video transcription and slide conversion to structured study notes.

## Features

- Downloads all Canvas course content (lectures, assignments, announcements, discussions) via REST API
- Cleans and restructures raw markdown by removing broken links and boilerplate text
- Builds week-based Obsidian vault with auto-generated study files per week (Lecture Summary, Key Concepts, Flashcards, Study Guide)
- Transcribes YouTube videos using Claude API to create Video Notes.md with summaries and key terms
- Converts PDF/PPTX slides into structured Slide Notes.md with key concepts and takeaways
- Creates course indexes, assignment trackers, and exam preparation templates

## Tech Stack

- Python 3.11+
- Canvas LMS REST API
- Anthropic Claude API
- LibreOffice (for PPTX conversion)
- PyMuPDF4LLM (PDF text extraction)

## How to Run

1. Install dependencies: `pip install -r requirements.txt`

2. Set Canvas API token and Anthropic API key as environment variables

3. Run scripts in order:

```bash
python scripts/1_download_canvas.py
python scripts/2_clean_markdown.py
python scripts/3_build_vault.py
python scripts/4_transcribe_videos.py
python scripts/5_convert_slides.py
