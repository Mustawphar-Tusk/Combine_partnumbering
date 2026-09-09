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
//
// Environment-aware default: when the UI is opened from localhost (i.e. served
// by the local FastAPI at /ui), use same-origin ("") so it hits the LOCAL
// backend. Otherwise (Vercel-hosted) use the Render backend URL. This avoids
// having to manually flip this value between local testing and deployment.
(function () {
  var host = (typeof location !== "undefined" && location.hostname) || "";
  var isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  window.API_BASE = isLocal ? "" : "https://pump-configurator-api.onrender.com";
})();
