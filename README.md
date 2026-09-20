# Fuseline

Correlate **location data**, **browsing history**, and **app usage logs** into a unified UTC forensic timeline. Fuseline surfaces **proximity sessions** where those sources coincide in time, with full artifact provenance.

Workflow: **Acquisition → Analysis → Validation → Report**

| Service | URL |
|---------|-----|
| UI | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000 |
| OpenAPI | http://127.0.0.1:8000/docs |

---

## Problem statement

> Correlate location data, browsing history, and app usage logs into a unified forensic timeline.

| | |
|---|---|
| **Objective** | Chronological view of mobile activity across multiple artifact sources |
| **Stack** | Python, SQLite, optional Plaso import |
| **Approach** | Extract timestamps → normalize to UTC → correlate events → unified timeline |
| **Output** | Unified mobile forensic timeline with correlated sources |

---

## Features

- Case management with examiner metadata and per-case SQLite storage
- Ingest for app usage, Chromium history, location CSV/SQLite, and Plaso L2TCSV/JSONL
- SHA-256 hashing and content-addressed uploads
- UTC normalization and validation findings
- Proximity sessions (default ±5 minutes, ≥2 distinct sources)
- Swimlane timeline (Location / Browse / App) with event drawer and session highlight
- HTML, CSV, and JSON report export
- Bundled sample evidence for a working demo without live device images

---

## Quick start

```bash
git clone https://github.com/navneetxdd/fuseline.git
cd fuseline
```

### Dependencies

- Python 3.11+
- Node.js 18+

### Install

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
python scripts\seed_demo.py
cd frontend
npm install
cd ..
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_demo.py
cd frontend && npm install && cd ..
```

### Run

**Windows**

```powershell
.\scripts\run_dev.ps1
```

**Linux / macOS**

```bash
bash scripts/run_dev.sh
```

Open http://127.0.0.1:5173. The script starts the API and UI; the Vite proxy forwards `/api` to port 8000.

---

## Application workflow

### 1. Cases

1. Open **Cases**.
2. Enter case name, examiner, and timezone (default UTC).
3. Choose **Create & acquire** to create the case and continue to evidence ingest.
4. Or open an existing case and go to **Acquire**.

The active case appears in the top bar and scopes all subsequent operations.

### 2. Acquire

| Action | Result |
|--------|--------|
| **Load sample evidence** | Ingests `samples/demo_case/` (app DB, Chromium History, location CSV, Plaso sample) |
| **Upload** | Drag-and-drop or file picker; optional source hint (App / Browse / Location / Plaso / Auto) |
| Inventory | Original name, source type, SHA-256, event counts |

Uploads are hashed and stored under `data/uploads/<case_id>/`. Events are written to `data/cases/<case_id>.sqlite`.

### 3. Timeline (analysis)

1. Inspect **Location / Browse / App** swimlanes.
2. Select a mark or event-list row to open the detail drawer.
3. Open a **proximity session** to highlight correlated events across lanes.
4. Filter by source (empty sources are omitted).

### 4. Report (validation & export)

1. Review event, artifact, and session counts.
2. Read validation findings.
3. Export **HTML**, **CSV**, or **JSON**.

### Recommended walkthrough

1. Create a case → **Create & acquire**
2. **Load sample evidence** (~15 events, 4 artifacts, 4 sessions)
3. **Timeline** → open a session → inspect an event
4. **Report** → export HTML (and optionally CSV/JSON)

---

## Evidence formats

| Source | Formats |
|--------|---------|
| App usage | SQLite `app_usage` (`events` + `packages`), or UsageStats-style CSV/XML |
| Browsing | Chromium `History` SQLite (`urls` + `visits`) |
| Location | CSV or SQLite with latitude, longitude, and time columns |
| Plaso (optional) | `psort` L2TCSV or JSONL |

### Sample artifacts

`samples/demo_case/`

| File | Description |
|------|-------------|
| `app_usage.db` | App usage SQLite |
| `History` | Chromium browsing history |
| `location.csv` | GPS points |
| `plaso_sample.l2t.csv` | Minimal Plaso L2TCSV |

Regenerate samples:

```bash
python scripts/seed_demo.py
```

### Optional Plaso import

Plaso is not required at runtime. To import a Plaso timeline:

```bash
log2timeline.py --storage-file evidence.plaso /path/to/extraction
psort.py -o l2tcsv -w timeline.l2t.csv evidence.plaso
```

Upload `timeline.l2t.csv` on Acquire with source hint **Plaso**.

---

## Architecture

```
Acquire → parsers → UTC normalize → SQLite events
                                  → validation findings
                                  → proximity sessions (±5 min, ≥2 sources)
UI / report exports ← FastAPI
```

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| Storage | SQLite (WAL), one database per case |
| Parsers | Native Python (Plaso / ALEAPP–compatible schemas) |
| UI | Vite, React, TypeScript |
| Reports | Jinja2 HTML, CSV, JSON |

### API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` / `POST` | `/api/cases` | List / create cases |
| `POST` | `/api/cases/{id}/acquire` | Upload artifact |
| `POST` | `/api/cases/{id}/demo` | Load sample pack |
| `GET` | `/api/cases/{id}/timeline` | Timeline events |
| `GET` | `/api/cases/{id}/sessions` | Proximity sessions |
| `GET` | `/api/cases/{id}/report.html` | HTML report |
| `GET` | `/api/cases/{id}/report.csv` | CSV export |
| `GET` | `/api/cases/{id}/report.json` | JSON export |

Interactive reference: http://127.0.0.1:8000/docs

---

## Repository layout

```
backend/app/         API, parsers, pipeline, report templates
backend/tests/       pytest suite
frontend/src/        Cases, Acquire, Timeline, Report UI
samples/demo_case/   Demo evidence fixtures
scripts/             seed_demo.py, run_dev.ps1, run_dev.sh
docs/                Problem statement reference
data/                Runtime case DBs and uploads (gitignored)
```

---

## Tests

```bash
# Windows
.\.venv\Scripts\python -m pytest backend/tests -q

# Linux / macOS
pytest backend/tests -q
```

---

## Security

Designed for local examiner workstations:

- UUID case identifiers; upload paths constrained under `data/uploads/`
- Sanitized filenames; 64 MiB upload limit
- Duplicate ingest skipped by SHA-256
- SPA routing does not capture `/api/*`

Not intended as multi-tenant production hosting.

---

## Acknowledgments

Parser schemas informed by [Plaso](https://github.com/log2timeline/plaso) and [ALEAPP](https://github.com/abrignoni/ALEAPP). Related prior art: [imcom/Android-forensic-timeline](https://github.com/imcom/Android-forensic-timeline). No third-party forensic engines are vendored here.

---

## License

MIT — see [LICENSE](LICENSE).
