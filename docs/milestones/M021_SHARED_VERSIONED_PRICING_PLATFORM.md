# M021 — Shared Versioned Pricing Platform

$content = @'
# M021 — Shared Versioned Pricing Platform

**Status:** COMPLETE  
**Date:** 2026-08-07

## Objective

Implement a shared, metadata-driven pricing platform that supports
Fybroc today and can support Dean without creating a second pricing
engine.

Excel workbooks remain pricing metadata sources only.

Runtime pricing is resolved from versioned SQL metadata.

---

## Architecture

```text
Pricing Workbook
      |
      v
Pricing Metadata Compiler
      |
      v
Compiled JSON
      |
      v
stg.PricingExtract
      |
      v
price.PriceBook
price.PriceBookVersion
price.PriceRule
price.PriceCondition
      |
      v
SqlPricingRepository
      |
      v
PricingService
      |
      v
FastAPI finalize response
