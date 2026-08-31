# Deployment Milestone — Live Test Environment (Vercel + Render + ngrok)

Date: 2026-08-27

## Summary

The Fybroc pump configurator is deployed to a **shareable live test environment**
that engineering can exercise from a browser. The database remains on the local
machine (no cloud DB yet); it is reached through an ngrok TCP tunnel.

```
  [ Vercel ]              [ Render (Docker) ]            [ Local PC ]
  static UI      ─────►    FastAPI backend      ─────►    ngrok TCP  ──► SQL Server
  configurator.html        (pyodbc + ODBC 18)            tunnel 1433    PumpConfiguratorDB
```

- UI (Vercel):     https://combine-partnumbering-claude.vercel.app
- API (Render):    https://pump-configurator-api.onrender.com
- Repo:            github.com/Mustawphar-Tusk/Combine_partnumbering_Claude
- Verified end-to-end: series list, evaluate (constrained options), and part-
  number resolution all return correctly through the full chain.

## Why this topology

Vercel's serverless Python runtime cannot run pyodbc (no system ODBC driver, no
long-lived process). So the split is:
- **Vercel** hosts only the static UI.
- **Render** runs the FastAPI backend in a Docker image that bakes in Microsoft
  ODBC Driver 18.
- **ngrok** exposes the local SQL Server so Render can reach it without a cloud
  database.

## Artifacts added this session

| File | Purpose |
|------|---------|
| `Dockerfile` | Backend image: python:3.14-slim + msodbcsql18 + deps; runs uvicorn on `$PORT` |
| `.dockerignore` | Excludes workbooks, secrets, `.venv`, `.db` from the image |
| `render.yaml` | Render blueprint (Docker web service); secret env vars `sync:false` |
| `vercel.json` | Serves `ui/` static folder; redirects `/` -> `/configurator.html` |
| `ui/config.js` | Sets `window.API_BASE` (backend origin); default `""` = same-origin |
| `ui/configurator.html` | API base parameterized via `window.API_BASE` |
| `DEPLOYMENT.md` | Full setup + ngrok restart guide |

## Fixes made during bring-up

1. **Linux build failure** — `requirements.txt` listed `pywin32` unconditionally;
   guarded it with `; sys_platform == 'win32'` so the Render/Linux build skips it.
2. **Vercel root 404** — `/` returned 404 (rewrite + cleanUrls conflict); switched
   to a redirect `/` -> `/configurator.html`.
3. **Per-step latency** — evaluate/validate/resolve opened TWO DB connections per
   request (one for the publication lookup, one for the handler). Now reuses a
   single connection and caches the active publication (60s TTL), halving the
   TCP+TLS+SQL-login handshakes over the tunnel.

## Runtime prerequisites (must be up during testing)

1. SQL Server running (auto-starts with Windows).
2. ngrok tunnel running: `ngrok tcp 1433`.
3. Render `DB_SERVER` env var matching the CURRENT ngrok host,port (free-tier
   address changes each restart — see DEPLOYMENT.md "Restarting the ngrok tunnel").
4. Render service awake (free tier sleeps when idle; first request ~30-60s).

Environment variables set in the Render dashboard (not in git):
`DB_SERVER` (ngrok host,port), `DB_USERNAME`, `DB_PASSWORD`,
`CONFIGURATION_TOKEN_SECRET`. `DB_DATABASE`/`DB_DRIVER`/`API_ENVIRONMENT` come
from `render.yaml`.

## Limitations of this environment

- **Tied to the local machine**: the URL only works while SQL Server + ngrok +
  Render are all live. Suitable for a coordinated/supervised test window, not
  unattended 24/7 access.
- **Free-tier characteristics**: Render cold starts; ngrok address rotates on
  restart; tunnel adds network latency per request.

## Recommended next step (when unattended access is needed)

Move the database to **Azure SQL** (hosted): removes ngrok and the local-PC
dependency, gives a stable address, and lets the team test anytime. Seed it with
the loaders in `scripts/` (load_all_series.py, load_motor_constraints_to_sql.py,
load_combine_variables_to_sql.py, load_item_applicability_to_sql.py, etc.).
Optionally keep Render warm (paid tier or an uptime pinger) to remove cold starts.

## Security notes

- Secrets live only in the Render dashboard; `.env`, `.db`, and workbooks are
  git- and docker-ignored. A prior audit confirmed no secrets/workbooks are
  tracked in the repo.
- Exposing SQL Server over a public tunnel: uses a least-privilege SQL login
  (`configurator_test`, not `sa`) with a strong password; stop ngrok when not
  testing. The ngrok authtoken shared during setup should be rotated.
