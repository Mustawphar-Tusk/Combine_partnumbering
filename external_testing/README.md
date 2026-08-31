# External Testing — Deployment Configuration Index

This folder is the single place to find everything about the external test
deployment (the shareable Vercel UI + Render API + ngrok-to-local-DB setup).

Some platform config files MUST live at the repository root (Vercel, Render, and
Docker only look for them there) and therefore are NOT moved into this folder.
This README indexes them so you still have one place to understand the whole
setup.

## Live environment

| Piece | URL / value |
|-------|-------------|
| UI (Vercel)  | https://combine-partnumbering-claude.vercel.app |
| API (Render) | https://pump-configurator-api.onrender.com |
| Repo         | github.com/Mustawphar-Tusk/Combine_partnumbering_Claude |
| Database     | Local SQL Server `PumpConfiguratorDB`, reached via ngrok TCP tunnel |

## Documentation (in this folder)

| File | What it is |
|------|-----------|
| `external_testing/DEPLOYMENT.md` | Full setup + operations guide: SQL Server prep, ngrok tunnel, Render, Vercel, end-to-end test, and the ngrok restart procedure. |
| `docs/evidence/DEPLOYMENT_MILESTONE.md` | The milestone record: topology, artifacts, bring-up fixes, limitations, security notes, and the Azure-SQL next step. |

## Platform config files (must stay at repo ROOT — do NOT move)

| File (at repo root) | Used by | Why it must stay at root |
|---------------------|---------|--------------------------|
| `Dockerfile` | Render | Builds the FastAPI image (python 3.14 + ODBC Driver 18). `render.yaml` references it by root path. |
| `.dockerignore` | Docker build | Docker only reads `.dockerignore` from the build-context root. Excludes workbooks/secrets/.venv from the image. |
| `render.yaml` | Render | Render auto-detects the Blueprint only at the repo root. Defines the `pump-configurator-api` Docker web service and its env vars. |
| `vercel.json` | Vercel | Vercel only reads a root `vercel.json`. Serves the `ui/` folder and redirects `/` -> `/configurator.html`. |
| `ui/config.js` | The deployed UI | Sets `window.API_BASE` (the Render backend URL). Must stay in `ui/` because `ui/` is the deployed site. |
| `ui/configurator.html` | The deployed UI | The configurator page itself. |

## Render environment variables (set in the Render dashboard, NOT in git)

| Key | Value | Notes |
|-----|-------|-------|
| `DB_SERVER` | e.g. `8.tcp.ngrok.io,12501` | ngrok host,port (comma, not colon). Changes each ngrok restart on the free tier. |
| `DB_USERNAME` | `configurator_test` | Least-privilege SQL login. |
| `DB_PASSWORD` | (secret) | Set only in Render. |
| `CONFIGURATION_TOKEN_SECRET` | (secret, >= 32 chars) | Token signing secret. |
| `DB_DATABASE`, `DB_DRIVER`, `API_ENVIRONMENT` | from `render.yaml` | Non-secret; defined in the blueprint. |

## Daily operating checklist (test window)

1. Ensure SQL Server is running (auto-starts with Windows).
2. Start the tunnel: `ngrok tcp 1433` (leave it open).
3. If the ngrok address changed, update `DB_SERVER` in Render and let it
   redeploy. See "Restarting the ngrok tunnel" in `external_testing/DEPLOYMENT.md`.
4. Wake Render (first request after idle ~30-60s): open the UI or `<api-url>/docs`.
5. Share the Vercel URL with testers (only works while the above are live).

## Recommended next step

For unattended, anytime team testing, migrate the database to Azure SQL — removes
ngrok and the local-PC dependency and is faster (Render talks directly to a cloud
DB). Seed it with the loaders in `scripts/`. See the milestone doc for details.
