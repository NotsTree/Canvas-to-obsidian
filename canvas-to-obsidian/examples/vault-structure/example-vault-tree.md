# Example Vault Structure

After running all five scripts, your Obsidian vault looks like this:

```
University/
├── Home.md                          ← Dashboard — links to all courses
├── .obsidian/
│   ├── app.json
│   └── community-plugins.json       ← Dataview + Spaced Repetition pre-configured
│
├── _Templates/
│   ├── Lecture Summary.md
│   ├── Key Concepts.md
│   ├── Flashcards.md
│   └── Study Guide.md
│
├── Concepts/                        ← Cross-course atomic notes
│   ├── OOP Principles.md
│   ├── Relational Model.md
│   ├── System Design.md
│   └── Wireless Fundamentals.md
│
└── Courses/
    └── ICT211 — Database Design/
        ├── ICT211 — Database Design.md   ← Course index
        │
        ├── Week 1 — Introducing Databases and Database Modelling/
        │   ├── Lecture Summary.md        ← Full lecture content
        │   ├── Key Concepts.md           ← Bullets + key terms table
        │   ├── Flashcards.md             ← Q&A with #flashcard tags
        │   ├── Study Guide.md            ← Checklist + learning outcomes
        │   ├── Video Notes.md            ← Generated from YouTube transcripts  (script 4)
        │   └── Slide Notes.md            ← Generated from PDF slides           (script 5)
        │
        ├── Week 2 — Database Modelling/
        │   └── ...
        │
        ├── Assignments/
        │   ├── _Assignments Index.md
        │   └── Task_1_Information.md
        │
        └── Exam Prep/
            └── Exam Prep — ICT211.md
```

## What each file contains

| File | Source | Contents |
|------|--------|----------|
| `Lecture Summary.md` | Canvas pages | Full lecture text, re-levelled headings |
| `Key Concepts.md` | Canvas pages | Extracted bullets, bold terms table |
| `Flashcards.md` | Canvas pages | Auto-generated Q&A, `#flashcard` tagged |
| `Study Guide.md` | Canvas pages | Learning outcomes checklist, week overview |
| `Video Notes.md` | YouTube transcripts + Claude | Overview, key concepts, timestamped transcript |
| `Slide Notes.md` | PDF/PPTX + Claude | Slide-by-slide notes, key terms, diagrams |
