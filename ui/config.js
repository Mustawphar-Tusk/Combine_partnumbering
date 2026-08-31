// UI runtime configuration.
//
// API_BASE is the origin of the FastAPI backend (NO trailing slash, NO /api/v2).
//
//  - Local development (API serves the UI at /ui): leave this empty ("").
//    The UI then calls the API same-origin at /api/v2/...
//
//  - Vercel-hosted UI calling the Render-hosted API: set this to the backend's
//    public URL, e.g.:
//        window.API_BASE = "https://pump-configurator-api.onrender.com";
//
// For Vercel, override this value at deploy time (see DEPLOYMENT.md) so the
// static UI knows where the backend lives.
window.API_BASE = "https://pump-configurator-api.onrender.com";
