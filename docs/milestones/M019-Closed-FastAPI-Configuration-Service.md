# M019 – Closed FastAPI Configuration Service

## Objective

Expose the completed allowable-configuration and persistence workflow
through a stable local HTTP boundary for Excel and the future web
application.

## Operations

The service exposes exactly three configuration operations:

1. Start a family configuration.
2. Advance with a server-issued state token and option token.
3. Finalize and persist a completed signed state.

## Closed Request Boundary

No endpoint accepts:

- an engineering field name
- an engineering display value
- a selection dictionary
- an identifier segment
- a Part Number or SKU to persist

Part Number and SKU remain server generated.

## Runtime Ownership

The FastAPI lifespan builds the Fybroc persistence runtime once when
the service starts. Requests reuse that runtime registry.

## Request Models

Pydantic models:

- reject extra fields
- expose camel-case JSON
- enforce token length limits
- keep `requestedBy` outside the engineering payload as an audit header

## Local-First Deployment

The initial service should bind to `127.0.0.1`. This supports Phase 1
Excel integration without exposing the API to the network.

Authentication, TLS termination, and remote hosting are separate
deployment milestones.
