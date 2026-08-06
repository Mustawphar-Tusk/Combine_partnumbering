# Phase 1 Scope

Phase 1 creates a metadata-driven SQL Server and FastAPI service for Dean and Fybroc.

For every valid configuration, the service must create or reuse:

- Part Number
- SKU
- Quote Price

When no active price matches, the API returns numeric price `0` and pricing status `not_found`. Missing pricing does not prevent a valid configuration from receiving a Part Number and SKU.

Excel VBA will call the API and write results to each family's own Formal Quote sheet using metadata-based output mappings.
