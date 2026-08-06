# M019 Closed FastAPI Contract

## Design Rule

The API does not accept engineering field/value selections.

The client can perform only three configuration operations:

```text
Start
→ Advance with issued state and option tokens
→ Finalize and persist a completed signed state
```

## 1. Start

```http
POST /api/v1/families/FYBROC/configurations/start
Content-Type: application/json

{}
```

Response:

```json
{
  "familyCode": "FYBROC",
  "runtimeRevision": "publication:1;series-batch:2;combination-batch:2;dependency-batch:1",
  "stateToken": "<signed-state-token>",
  "complete": false,
  "nextFieldCode": "SERIES",
  "selectionCount": 0,
  "options": [
    {
      "fieldCode": "SERIES",
      "displayValue": "1530 (ANSI)",
      "optionToken": "<signed-option-token>"
    }
  ]
}
```

## 2. Advance

```http
POST /api/v1/families/FYBROC/configurations/advance
Content-Type: application/json

{
  "stateToken": "<signed-state-token>",
  "optionToken": "<signed-option-token>"
}
```

The request contains no `fieldCode` or `value`. Both are already bound
inside the signed option token.

## 3. Finalize and Persist

```http
POST /api/v1/families/FYBROC/configurations/finalize
Content-Type: application/json
X-Requested-By: DOMAIN\user

{
  "stateToken": "<completed-signed-state-token>"
}
```

Response:

```json
{
  "configuredProductRegistryId": 1,
  "wasCreated": false,
  "configurationSignature": "bb793b...",
  "partNumber": "F1530-B-1-1-AA-0001-0Y-1Q-002-XXX-T00",
  "sku": "F1530-V1-B11AA00010Y1Q002XXXT00",
  "requestCount": 12,
  "runtimeRevision": "publication:1;series-batch:2;combination-batch:2;dependency-batch:1",
  "metadataPublicationId": 1,
  "seriesBatchId": 2,
  "combinationBatchId": 2,
  "dependencyBatchId": 1,
  "selectionCount": 41,
  "segmentCount": 10,
  "createdAt": "2026-08-04T22:00:00Z",
  "lastRequestedAt": "2026-08-04T22:05:00Z"
}
```

## Rejected Payloads

These are not part of the API contract:

```json
{
  "fieldCode": "SIZE",
  "value": "6x10x8"
}
```

```json
{
  "selections": {
    "SERIES": "1530",
    "SIZE": "6x10x8"
  }
}
```

Pydantic request models use `extra="forbid"`, so attempts to add these
fields return HTTP 422 before the configuration engine is called.

## Defensive Conflicts

HTTP 409 is reserved for defensive conditions such as:

- stale or tampered tokens
- a token issued for a different state
- an incomplete state submitted for finalization
- metadata revision conflicts
- persistence signature conflicts

These are integrity safeguards, not a user-facing invalid-selection
workflow.
