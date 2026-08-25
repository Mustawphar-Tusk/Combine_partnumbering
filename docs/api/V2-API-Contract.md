# V2 Pump Configuration API Contract

**Version:** 2.1  
**Date:** 2026-08-25  
**Status:** Active  
**Base Path:** `/api/v2`  

---

## Overview

The V2 API provides a direct, cacheable interface for pump configuration. It is designed as a **unified interaction layer** that serves both Excel (VBA) and React (web UI) clients identically.

**Architecture principle:** Both clients perform the same operation:
```
User selects a value → API returns ONLY what's still valid
```

Whether the selection happens in an Excel cell or a React dropdown is irrelevant to the API. The response is identical — a list of allowable options per remaining field.

**Excel interaction flow:**
```
Excel cell change → VBA collects all current values → ONE POST /evaluate → 
VBA writes allowable options into data-validation lists for remaining cells
```

**React interaction flow:**
```
Dropdown selection → React collects form state → ONE POST /evaluate →
React re-renders remaining dropdowns with only valid choices
```

**Key design decisions:**
- In-memory caching (5-minute TTL, keyed on publication ID)
- Single-request evaluate replaces V1's multi-step token navigation
- Direct field/value input — no opaque tokens needed
- Both families (Fybroc + Dean) through same endpoint structure
- Only allowable configurations are ever returned — invalid options are never shown

---

## Endpoints

### 1. GET Configuration Dictionary

```http
GET /api/v2/families/{family}/configuration-dictionary
```

Returns the complete runtime configuration dictionary for a pump family. **Cached** — repeated requests within the cache TTL return instantly without database access.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| family | string | `FYBROC` or `DEAN` |

**Response:** `200 OK`

```json
{
  "family": "FYBROC",
  "publication_version": "F140-corrections-v1",
  "publication_id": 2,
  "cached": true,
  "field_count": 55,
  "fields": [
    {
      "field_code": "PUMP_MATERIAL",
      "series_options": {
        "1500": ["vr-1", "vr-1a", "ey-2", "vr-1 bpo/dma", "vr-1a bpo/dma", "vr-1v"],
        "1530": ["vr-1", "vr-1a", "ey-2"],
        "1600": ["vr-1", "vr-1a", "ey-2", "vr-1 bpo/dma"]
      }
    }
  ]
}
```

**Cache behavior:**
- Keyed on `(family, publication_id)` — auto-invalidates when a new publication is activated
- TTL: 5 minutes (configurable)
- `cached: true` in response indicates data was served from cache

---

### 2. POST Evaluate Configuration

```http
POST /api/v2/families/{family}/configurations/evaluate
Content-Type: application/json
```

Evaluate a partial configuration: returns allowable options for remaining fields based on current selections and constraints. **Not cached** (input-dependent).

**Request Body:**

```json
{
  "series": "1500",
  "selections": {
    "PUMP_MATERIAL": "vr-1a",
    "SIZE": "1x2x10"
  }
}
```

**Response:** `200 OK`

```json
{
  "family": "FYBROC",
  "series": "1500",
  "valid": true,
  "allowable_options": {
    "IMPELLER_TRIM": ["4.000", "4.125", "4.250", "..."],
    "FLUSH": ["external flush", "internal flush", "bypass (tapped discharge)"],
    "SEAL_TYPE": ["8-1t double inside", "8b2 single outside", "..."]
  },
  "resolved_codes": {
    "PUMP_MATERIAL": "5",
    "SIZE": "3"
  },
  "errors": []
}
```

---

### 3. POST Validate Configuration

```http
POST /api/v2/families/{family}/configurations/validate
Content-Type: application/json
```

Validate a complete configuration against all constraints. Returns violations if any selections are invalid for the series. **Not cached.**

**Request Body:**

```json
{
  "series": "1500",
  "selections": {
    "PUMP_MATERIAL": "vr-1a",
    "SIZE": "1x2x10",
    "IMPELLER_TRIM": "9.250",
    "FLUSH": "external flush",
    "SEAL_TYPE": "8-1t double inside"
  }
}
```

**Response (valid):** `200 OK`

```json
{
  "family": "FYBROC",
  "series": "1500",
  "valid": true,
  "violations": []
}
```

**Response (invalid):** `200 OK`

```json
{
  "family": "FYBROC",
  "series": "1500",
  "valid": false,
  "violations": [
    {
      "field": "IMPELLER_TRIM",
      "value": "99.000",
      "reason": "'99.000' is not a valid option for IMPELLER_TRIM in series 1500"
    }
  ]
}
```

---

### 4. POST Resolve Configured Product

```http
POST /api/v2/families/{family}/configured-products/resolve
Content-Type: application/json
```

Resolve a complete configuration into a Part Number, SKU, and configured product. Performs reuse detection — if the same configuration was resolved before, returns the existing product. **Not cached** (creates side effects).

**Request Body:**

```json
{
  "series": "1500",
  "selections": {
    "SERIES": "1500",
    "FLANGE_TYPE": "ANSI",
    "SIZE": "1x2x10",
    "PUMP_MATERIAL": "VR-1A",
    "IMPELLER_TRIM": "9.250"
  },
  "segment_codes": {
    "PUMP_OPTIONS": "1VC1",
    "SEAL_MFG": "S",
    "SEAL_ASSY": "03",
    "OPTIONS": "3G",
    "FRAME_SIZE": "04",
    "MOTOR_ASSY": "XXX",
    "MOTOR_MODS": "XXX",
    "TESTING": "00"
  },
  "requested_by": "DOMAIN\\user"
}
```

**Response (new product):** `200 OK`

```json
{
  "family": "FYBROC",
  "part_number": "FA35FC-1VC1-S03-3G-04XXX-XXX-00",
  "sku": "F1500-A1B2C3D4A",
  "configuration_signature": "BB793B4F...(64 hex chars)",
  "existing_configuration": false,
  "configured_product_id": null,
  "pricing": [
    {"component": "Base Pump", "amount": 17252.00, "detail": "VR-1A (Standard)"}
  ],
  "total_price": 17252.00,
  "segment_debug": {
    "brand": "F",
    "series_code": "A",
    "size_code": "3",
    "material_code": "5",
    "trim_code": "FC",
    "pump_options": "1VC1",
    "seal_mfg": "S",
    "seal_assy": "03",
    "options": "3G",
    "frame_size": "04",
    "motor_assy": "XXX",
    "motor_mods": "XXX",
    "testing": "00",
    "is_vertical": false,
    "failed_segments": []
  }
}
```

**Response (reused product):** `200 OK`

```json
{
  "family": "FYBROC",
  "part_number": "FA35FC-1VC1-S03-3G-04XXX-XXX-00",
  "sku": "F1500-A1B2C3D4A",
  "configuration_signature": "BB793B4F...",
  "existing_configuration": true,
  "configured_product_id": 42,
  "pricing": [
    {"component": "Base Pump", "amount": 17252.00, "detail": "VR-1A (Standard)"}
  ],
  "total_price": 17252.00,
  "segment_debug": {}
}
```

**Segment Debug:** The `segment_debug` object is included in all resolve responses to aid development troubleshooting. It shows how each Part Number segment was resolved, which segments failed lookup, and whether the configuration is for a vertical series (where seal segment is omitted).

**Pricing:** The `pricing` array contains all matched price rules for the configuration. `total_price` is the sum. If no pricing rules match, the array is empty and `total_price` is 0.

---

## V1 Endpoints (Maintained for Compatibility)

V1 uses signed tokens for navigation and is retained for existing Excel VBA clients.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/families/{family}/configurations/start` | POST | Begin token-based configuration |
| `/api/v1/families/{family}/configurations/advance` | POST | Advance with state+option tokens |
| `/api/v1/families/{family}/configurations/finalize` | POST | Persist completed configuration |

V1 will be deprecated after all clients migrate to V2.

---

## Error Responses

All errors follow a standard format:

```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable description"
  }
}
```

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 404 | `pump_family_not_configured` | Family not found |
| 409 | `configuration_state_conflict` | Configuration cannot be advanced |
| 409 | `configured_product_conflict` | Persistence conflict |
| 422 | `request_schema_violation` | Invalid request body |
| 503 | `database_unavailable` | SQL Server temporarily unavailable |
| 503 | `service_configuration_error` | API misconfigured |

---

## SKU Format

Both families use the same SKU format:

```
<FamilyPrefix><Series>-<8char_deterministic_token><VersionLetter>
```

- **Fybroc:** `F1500-A1B2C3D4A` (F = Fybroc, 1500 = series, A1B2C3D4 = SHA-256 derived, A = version 1)
- **Dean:** `D2110-X7Y8Z9W0A` (D = Dean, 2110 = series, X7Y8Z9W0 = SHA-256 derived, A = version 1)

Version letters: A=1, B=2, C=3... (increments on re-configuration)

SKU uniquely identifies one Part Number → one Configuration → one BOM.

---

## Part Number Format

Unified segment sequence (separator = `-`):

**Horizontal (1500, 1530, 1600, 1630, 2530, 3000):**
```
<Brand><SeriesCode><Size><Material><Trim>-<WetEndOptions>-<SealMfg><SealAssy>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>
```

**Vertical (5500, 5530, 7500, 8500):**
```
<Brand><SeriesCode><Size><Material><Trim>-<WetEndOptions>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>
```

Note: Vertical pumps omit the seal segment entirely (they do not have seal assemblies).

**Fybroc horizontal example:** `FA35FC-1VC1-S03-3G-04XXX-XXX-00`  
**Fybroc vertical example:** `FG42GB-07HO-02-32049-XXX-00`  
**Dean example:** `D610-00CA-AB01-ERR-TBD__-07617-0V03L-0KN00-00-1Z1IJ4`

---

## Authentication

U170 milestone will implement Microsoft Entra ID (Azure AD) authentication with the following roles:
- **Engineering** — publish metadata and pricing
- **Pricing** — manage price rules
- **Sales/Configurator** — configure products and create quotes

Currently the API runs without authentication (development mode).

---

## Caching Strategy

| Resource | Cached | Key | TTL | Invalidation |
|----------|--------|-----|-----|-------------|
| Configuration Dictionary | ✅ | `(family, publication_id)` | 5 min | Publication change |
| Attribute Codes | ✅ | `(family, publication_id)` | 5 min | Publication change |
| Evaluate | ❌ | — | — | Input-dependent |
| Validate | ❌ | — | — | Input-dependent |
| Resolve | ❌ | — | — | Side effects |
