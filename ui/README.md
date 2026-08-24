# UI — Pump Configurator Frontend

All user interface files for the pump configurator live here.

## Structure

```
ui/
├── configurator.html       # Test UI (served at /ui/configurator.html)
├── components/             # React components (for production build)
│   └── PumpConfigurator.tsx
└── README.md
```

## Running the Test UI

1. Start the FastAPI server:
   ```
   uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Open in browser:
   ```
   http://localhost:8000/ui/configurator.html
   ```

3. Select a Family (Fybroc/Dean) and Series, then configure the pump.
   Each dropdown shows ONLY allowable options based on current selections.

## How It Works

- The HTML page calls `POST /api/v2/families/{family}/configurations/evaluate`
- Each selection change triggers a fresh evaluate call
- The response contains `allowable_options` — only valid remaining choices
- When ready, click "Generate Part Number & SKU" to resolve the product

## Shared API

Both this UI and the Excel VBA client call the **same API endpoints**.
The API is client-agnostic — it returns identical responses regardless
of whether the caller is a browser, Excel, or any HTTP client.
