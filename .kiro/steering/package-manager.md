# Package manager conventions

**Status:** always-on. Governs how Python and JavaScript dependencies are managed
and how code is executed, so the project's lockfiles stay authoritative and
environments are reproducible.

## Python — use `uv` (never pip directly)

This project is `uv`-managed: `pyproject.toml` + `uv.lock` are authoritative, and
`uv` is on PATH. The virtual environment lives at `.venv`.

- **Run code with `uv run`:**
  - Scripts/probes: `uv run python scripts/<name>.py`
  - One-liners: `uv run python -c "..."`
  - The API server:
    `uv run python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080`
  - `uv run` resolves the SAME interpreter as `.venv\Scripts\python.exe`, so this
    is a drop-in for prior direct-interpreter calls.
- **Add/remove/upgrade dependencies with `uv`:**
  - Add: `uv add <pkg>` (pins into `pyproject.toml` + updates `uv.lock`).
  - Dev-only: `uv add --dev <pkg>`.
  - Remove: `uv remove <pkg>`. Sync an env: `uv sync`.
  - NEVER `pip install` into the venv — it bypasses the lockfile and drifts the
    environment. `requirements.txt` (if present) is secondary to `uv.lock`.
- Pin exact/compatible versions; prefer well-known, maintained packages; flag any
  unusual or possible typosquat package name before adding.

### When invoking the API for audits/tests
- Start it with `uv run python -m uvicorn ...` (set `PYTHONPATH="."`,
  `CONFIGURATION_TOKEN_SECRET`, etc. as before).
- The Fybroc gate (`run_all_fybroc_audits.py`) still needs port 8080 FREE before it
  runs, so stop any `uv run` uvicorn first (unchanged by this rule).

## JavaScript / frontend — use `npm` for `spa/`

The `spa/` project (Vite + React + TypeScript) is a separate ecosystem that `uv`
does not manage. Use `npm` there:
- Install: `npm install` (in `spa/`). Build: `npm run build`. Dev server: `npm run dev`.
- `package.json` + `package-lock.json` are authoritative for JS deps.
- `spa/node_modules`, `spa/dist`, and `*.tsbuildinfo` are gitignored; a fresh
  checkout must `npm install && npm run build` in `spa/` before `/app` serves.
- Do NOT use `uv` for JS packages, and do NOT commit `node_modules` or `dist`.

## Quick reference
| Task | Command |
|------|---------|
| Run a Python script | `uv run python scripts/x.py` |
| Run the API | `uv run python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080` |
| Add a Python dep | `uv add <pkg>` |
| Sync Python env | `uv sync` |
| Install SPA deps | `npm install` (in `spa/`) |
| Build the SPA | `npm run build` (in `spa/`) |
