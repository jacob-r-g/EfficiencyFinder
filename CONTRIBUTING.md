# Contributing

Thanks for taking an interest in EfficiencyFinder. Small, focused pull requests are easiest to review.

## Development setup

**Python 3.10+** is required for the analysis engine, desktop app, and API. **Node.js 20+** is required for the web frontend.

### Desktop app

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

### Web backend + frontend

```bash
python3 -m pip install -r web/backend/requirements.txt
PYTHONPATH=. python3 -m uvicorn web.backend.app:app --reload --port 8000
```

```bash
cd web/frontend
npm install
npm run dev
```

Vite proxies API calls to port 8000 during local development.

### Tests

```bash
python3 -m pip install -r requirements.txt -r web/backend/requirements.txt
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Frontend typecheck/build:

```bash
cd web/frontend && npm ci && npm run build
```

## Project layout

| Path | Role |
|------|------|
| `core/` | Analysis engine (no GUI deps) |
| `gui/` | PySide6 desktop UI |
| `web/backend/` | FastAPI upload + job API |
| `web/frontend/` | React (Vite) SPA |
| `tests/` | `unittest` suite |
| `examples/` | Tiny synthetic FASTA/FASTQ for demos |

## Pull requests

1. Branch from `main`.
2. Keep changes scoped; match existing style.
3. Add or update tests when behavior changes.
4. Bump `VERSION` (and `web/frontend/package.json` version) when shipping a user-visible release.
5. Update `CHANGELOG.md` for notable changes.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
