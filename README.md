# MindVault

A premium-dark personal note-taking, journaling, drawing & document workspace.
Built with **Flask + SQLAlchemy + SQLite + vanilla JS/HTML5 Canvas**.

## Features
- 🔐 Auth (register, login, logout, hashed passwords, sessions)
- 🏠 Glassmorphic dark dashboard with stats & recent items
- 📓 Rich-text journal editor (bold/italic/underline/headings/lists/align/undo), auto-save, folders, tags, search
- ✏️ Drawing canvas: pen / pencil / brush / eraser, color picker, size, background, mouse/touch/stylus
- 📁 Document workspace: drag-and-drop upload, preview, download, delete (PDF/DOC/PPT/TXT/Images)
- 🗂 SQLite tables: Users, Journals, Drawings, Documents, Categories
- 🧩 Modular code — ready to extend with AI features later (PDF summary, Q&A, study planner)

## Run

```bash
cd MindVault
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000

## Project structure

```
MindVault/
├── app.py                # Flask app, routes, models
├── requirements.txt
├── database.db           # auto-created
├── uploads/              # user-uploaded documents
├── static/
│   ├── css/style.css
│   ├── drawings/         # saved drawing PNGs (auto-created)
│   └── images/
└── templates/
    ├── base.html
    ├── _app.html         # authenticated layout w/ sidebar
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── journals.html
    ├── journal_edit.html
    ├── drawings.html
    ├── drawing_edit.html
    └── documents.html
```

## Extend with AI (future)
The models and routes are intentionally modular. Drop an `ai/` package and hook
endpoints like `/api/ai/summarize`, `/api/ai/ask`, `/api/ai/plan` — pass the
Document or Journal record to your provider (OpenAI, Anthropic, local LLM).

## Security notes
- Passwords hashed via Werkzeug PBKDF2
- File uploads restricted by extension + 25 MB cap + UUID stored names
- Per-user ownership checks on every record
- Set `MINDVAULT_SECRET` env var in production
