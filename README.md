# CVENGINE

Local-first, macOS-first ATS / AI-HR resume engine. Compare a job posting to your master CV, tailor the resume **without inventing facts**, and keep application history in SQLite on your machine.

Data never leaves your computer. The core engine does not require an LLM. If [Ollama](https://ollama.com) is available, it is used only for light sentence polish; if the groundedness gate fails, the rule engine takes over.

> **UI language:** The product UI is currently Turkish. Docs and repo metadata are in English.

## Features

- Master CV ingest (PDF, DOCX, or JSON Resume)
- Job-posting tailor: reorder bullets, align skill wording, extractive summary — no fabricated employers, tools, or claims
- ATS parse signals + AI-HR heuristics + groundedness gates (tailored output targets **ATS ≥ 80**)
- Templates: Classic ATS, Executive, Compact — export PDF or DOCX
- Application dashboard backed by local SQLite
- Optional Ollama polish with automatic fallback to the rule engine
- Optional macOS login autostart via LaunchAgent

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Node 20+
- (desktop `.app` package) Rust / Cargo

## Quick start

```bash
chmod +x scripts/start.sh scripts/dev.sh
./scripts/start.sh
```

Or for hot-reload development:

```bash
./scripts/dev.sh
```

| Service | URL |
|---------|-----|
| UI | http://127.0.0.1:5173 |
| API health | http://127.0.0.1:8765/api/health |
| SQLite | `~/Library/Application Support/CVENGINE/cvengine.db` |

Stop with `./scripts/stop.sh`.

### Engine tests

```bash
cd engine
uv sync --extra dev
uv run pytest -q
```

## Typical flow

1. Upload a **master CV** (PDF, DOCX, or JSON Resume)
2. Start a **new application** and paste the job posting
3. The engine analyzes, reorders bullets, aligns skill wording, and builds an extractive summary
4. ATS parse + AI-HR signals + groundedness gates run
5. Pick Classic ATS / Executive / Compact and download PDF or DOCX
6. The application is stored in the local dashboard

## Autostart (macOS)

To install a login LaunchAgent and a synced runtime copy:

```bash
./scripts/install-autostart.sh
```

This registers `com.cvengine.app`, keeps a runtime under `~/Library/Application Support/CVENGINE/runtime`, and starts API + UI via `./scripts/start.sh` at login. Source-tree changes can sync into that runtime automatically.

## Desktop (.app)

```bash
cd ui && npm install && npm run build
cd ../src-tauri && cargo tauri build
```

Tauri launches the Python engine with `uv run uvicorn` on `127.0.0.1:8765`. Production machines need `uv` on `PATH`.

## Stack

| Path | Role |
|------|------|
| `engine/` | FastAPI + SQLite + parsers / tailor / gates / PDF–DOCX |
| `ui/` | Vite + React + Tailwind (single premium theme) |
| `src-tauri/` | Native macOS window (Tauri) |
| `skills/ontology.json` | TR–EN skill synonyms |
| `scripts/` | `start.sh`, `dev.sh`, `stop.sh`, autostart helpers |
