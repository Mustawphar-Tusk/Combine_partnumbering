# UI — Pump Configurator Frontend

All user interface files for the pump configurator live here. The primary UI is
a single-file, dependency-free HTML page (`configurator.html`) that talks to the
FastAPI v2 API. A React component (`components/PumpConfigurator.tsx`) is kept for
a future production build.

## Structure

```
ui/
├── configurator.html       # The configurator UI (served at /ui/configurator.html)
├── config.js               # Runtime config: sets window.API_BASE (backend origin)
├── components/             # React component (for a future production build)
│   └── PumpConfigurator.tsx
└── README.md
```

## Running the UI

1. Start the FastAPI server (it also serves this UI at `/ui`):
   ```
   # PowerShell (Windows)
   $env:PYTHONPATH="."
   $env:CONFIGURATION_TOKEN_SECRET="local-dev-configuration-token-secret-0123456789"
   .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080
   ```
   (Any host/port works; `uv run uvicorn src.api.app:app --reload` is fine too.)

2. Open in a browser:
   ```
   http://127.0.0.1:8080/ui/configurator.html
   ```
   On first load after a UI change, do a hard refresh (Ctrl+F5). The page sends
   no-cache headers, but a browser may still hold an older copy.

3. Pick a **Family** (Fybroc / Dean) and a **Series**, then configure the pump.
   Every applicable field is an editable dropdown, pre-seeded to its STANDARD
   (STD) value, and shows only options that are valid given every other choice.

## `config.js` — pointing the UI at a backend

`config.js` sets `window.API_BASE` (the backend origin, no trailing slash, no
`/api/v2`). It is environment-aware:

- **Local / same-origin** (served by the local API at `/ui`): `API_BASE = ""`
  so the UI calls the API relatively at `/api/v2/...`.
- **Hosted UI → hosted API** (e.g. Vercel UI, Render API): `config.js` sets the
  absolute backend URL. Override it at deploy time (see `DEPLOYMENT.md`).

If `config.js` is absent, the UI falls back to same-origin (`""`).

## How it works (free-edit model)

The UI uses the **free-edit** endpoint, not a linear top-down walk:

- On a family/series change (or a field edit) the UI calls
  `POST /api/v2/families/{family}/configurations/resolve-state` with the full
  current selection set.
- The server returns a COMPLETE state: a value for every STD-seeded field, the
  constraint-correct `allowable_options` for every field (computed against all
  the OTHER selections, so upstream and downstream both stay editable),
  `ordered_fields` (authoritative order), `field_groups` (grouping — see below),
  per-field `resolved_codes` (PN segment codes), plus any `reset_fields`,
  `dropped_fields`, and `conflicts`.
- Selections are never silently changed: an incompatible pick is KEPT and
  reported in `conflicts` with recommended alternatives; fields that no longer
  apply are dropped and reported. The UI surfaces these as inline notices.
- Clicking **Generate Part Number & SKU** calls
  `POST /api/v2/families/{family}/configured-products/resolve`, which returns the
  Part Number, SKU, signature, and per-component pricing.

### Sectioned layout + grouping

- **Dean** responses include `field_groups`: the authoritative 10-group Dean
  Data Sheet structure (Pump Information, Impeller, Power Frame, Coupling, Pump
  Seal, Flush / Barrier / Cooling Plan, Motor, Baseplate, Testing &
  Documentation, Additional Options). The UI renders each group as its own
  section card in a two-column masonry layout (label-left / value-right rows).
  - Fields with no selectable option yet render as disabled **C/F** (Contact
    Factory) rows.
  - Component groups a `PUMP_CONFIGURATION` bundle excludes (Coupling /
    Baseplate / Motor) are omitted, not shown as C/F.
  - The Dean **Size** selector is sourced from `cfg.PumpModelReference` (Dean
    does not store size as a field option) and appears first in Pump Information.
- **Fybroc** has no defined grouping (`field_groups` is empty), so the UI renders
  a single flat "Configuration" section. Fybroc behavior is unchanged.

### SKU lookup

The "Look up a pump" panel takes a SKU and calls
`GET /api/v2/configured-products/by-sku/{sku}`. It returns the stored product
(family, series, Part Number, SKU, signature) and the exact configured field
values from its `CanonicalConfiguration`, rendered read-only in the same
sectioned layout. **Load into configurator** seeds a new configuration from the
looked-up product. Works for both families.

## Theme

Sky-blue palette with dark-grey buttons that show a light inset shadow when
pressed. Styles are inline in `configurator.html` (no build step, no external
CSS/JS dependencies).

## Shared API

This UI and the Excel VBA client call the **same** v2 API endpoints. The API is
client-agnostic — it returns identical responses regardless of whether the
caller is a browser, Excel, or any other HTTP client.
