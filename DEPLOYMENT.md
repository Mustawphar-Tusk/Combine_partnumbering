# Test Deployment: Vercel (UI) + Render (API) + ngrok (DB tunnel)

This sets up a shareable test environment without moving the database off your
machine.

```
  [ Vercel ]              [ Render (Docker) ]            [ Your PC ]
  static UI      ─────►    FastAPI backend      ─────►    ngrok TCP  ──► local SQL Server
  configurator.html        (pyodbc + ODBC 18)            tunnel (1433)   PumpConfiguratorDB
```

Why this split: pyodbc needs a system-level ODBC driver and a long-lived
process, which Vercel's serverless Python runtime cannot provide. So Vercel
serves only the static UI; Render runs the Python API in a Docker image that
bakes in ODBC Driver 18; ngrok exposes your local SQL Server so Render can reach
it.

Artifacts already in the repo:
- `Dockerfile` / `.dockerignore` - backend image with ODBC Driver 18
- `render.yaml` - Render blueprint (env vars set in dashboard)
- `vercel.json` - serves the `ui/` folder
- `ui/config.js` - sets `window.API_BASE` (backend URL) for the UI

---

## Part A - Prepare local SQL Server (one time)

ngrok exposes raw TCP, so the remote backend must use **SQL authentication**
(Windows/Trusted auth cannot cross the tunnel), and SQL Server must accept
TCP/IP.

1. **Enable TCP/IP**
   - Open *SQL Server Configuration Manager* -> *SQL Server Network
     Configuration* -> *Protocols for <instance>* -> set **TCP/IP = Enabled**.
   - In TCP/IP *Properties -> IP Addresses -> IPAll*, ensure **TCP Port = 1433**
     (clear any TCP Dynamic Ports value so it listens on 1433).
   - Restart the *SQL Server* service.

2. **Enable mixed-mode authentication**
   - In SSMS: right-click the server -> *Properties* -> *Security* ->
     **SQL Server and Windows Authentication mode** -> OK -> restart the service.

3. **Create a dedicated SQL login** (least privilege; do NOT use `sa`)
   ```sql
   CREATE LOGIN configurator_test WITH PASSWORD = 'use-a-strong-password-here';
   USE PumpConfiguratorDB;
   CREATE USER configurator_test FOR LOGIN configurator_test;
   -- Runtime needs read (and the SKU stored proc). Grant what the app uses:
   ALTER ROLE db_datareader ADD MEMBER configurator_test;
   GRANT EXECUTE ON SCHEMA::cfg TO configurator_test;  -- stored procs (e.g. usp_GenerateSKU)
   -- If resolve writes configured products, also:
   ALTER ROLE db_datawriter ADD MEMBER configurator_test;
   ```
   Record the username/password - Render will use them.

4. **Verify local connectivity** (optional sanity check)
   ```
   sqlcmd -S localhost,1433 -U configurator_test -P "<password>" -d PumpConfiguratorDB -Q "SELECT DB_NAME();"
   ```

## Part B - Start the ngrok TCP tunnel

1. Install ngrok and authenticate (one time): `ngrok config add-authtoken <token>`
2. Expose SQL Server:
   ```
   ngrok tcp 1433
   ```
3. ngrok prints a forwarding address like:
   ```
   Forwarding  tcp://0.tcp.ngrok.io:17654 -> localhost:1433
   ```
   The backend's `DB_SERVER` value is the host,port form: **`0.tcp.ngrok.io,17654`**
   (comma, not colon - that is the pyodbc/SQL Server convention).

   Note (free tier): this address changes every time ngrok restarts. When it
   changes, update `DB_SERVER` in Render (Part D). A paid reserved TCP address
   avoids this.

   Keep this terminal running and your PC on for the duration of the test.

## Part C - Deploy the backend to Render

1. Push the repo (already done) so Render can access it, or connect the repo in
   the Render dashboard.
2. New -> *Blueprint* -> select this repo. Render reads `render.yaml` and creates
   the `pump-configurator-api` Docker web service.
3. Set the secret env vars (marked `sync:false`) in the dashboard:
   - `DB_SERVER`   = the ngrok host,port from Part B (e.g. `0.tcp.ngrok.io,17654`)
   - `DB_USERNAME` = `configurator_test`
   - `DB_PASSWORD` = the strong password from Part A
   - `CONFIGURATION_TOKEN_SECRET` = any string >= 32 chars (e.g. a random 40-char token)
   - (`DB_DATABASE`, `DB_DRIVER`, `API_ENVIRONMENT` come from render.yaml)
4. Deploy. First build takes a few minutes (installs ODBC driver + deps).
5. When live, note the service URL, e.g. `https://pump-configurator-api.onrender.com`.
   Confirm it responds: open `<url>/docs` (the FastAPI Swagger page) - a 200 means
   the app booted. A DB error only appears when you call an endpoint (that is
   when it opens the tunnel connection).

## Part D - Deploy the UI to Vercel

The UI is the `ui/` folder; `vercel.json` serves it. It needs to know the
backend URL via `window.API_BASE`.

1. Set the backend URL in `ui/config.js`:
   ```js
   window.API_BASE = "https://pump-configurator-api.onrender.com";
   ```
   Commit and push (or set it in the Vercel dashboard before deploy).
2. In Vercel: *Add New -> Project* -> import this repo.
   - Framework preset: **Other**
   - `vercel.json` already sets output directory to `ui/`.
3. Deploy. Vercel gives a URL like `https://your-project.vercel.app`.
4. Open it - the configurator loads and its API calls go to the Render backend.

## Part E - End-to-end test

1. Ensure ngrok is running (Part B) and SQL Server is up.
2. Open the Vercel URL.
3. Pick a family/series (e.g. FYBROC / 1500) and step through the configuration.
4. Generate a part number - confirm the value returns (this proves UI -> Render
   -> ngrok -> local SQL round-trip works).

## Troubleshooting

- **`/docs` loads but endpoints 503 `database_unavailable`**: the tunnel or
  credentials are wrong. Recheck `DB_SERVER` (host,port with a comma), that
  ngrok is running, and the SQL login works locally (Part A step 4).
- **`DB_SERVER` stopped working**: ngrok restarted and issued a new address -
  update `DB_SERVER` in Render and redeploy (or just save the env var).
- **CORS errors in the browser console**: the API allows all origins by default
  (`allow_origins=["*"]`). If you later lock it down, add the Vercel domain.
- **Login failed for user**: mixed-mode auth not enabled, or the login lacks
  access to `PumpConfiguratorDB` (Part A steps 2-3).
- **Timeouts on first request**: Render free tier sleeps idle services; the
  first request after idle can take ~30-60s to wake.

## Security notes (test-only posture)

- Exposing SQL Server over a public tunnel means the address is reachable by
  anyone who learns it. Use a strong password, a least-privilege login (not
  `sa`), and stop ngrok when not testing.
- Do not commit real secrets. `DB_PASSWORD` and `CONFIGURATION_TOKEN_SECRET`
  live only in the Render dashboard; `.env`, `.db`, and workbooks are
  git-ignored and docker-ignored.
- For anything beyond short-lived testing, prefer Azure SQL (a hosted database)
  over the ngrok-to-local-DB approach - seed it with the loaders in `scripts/`.
