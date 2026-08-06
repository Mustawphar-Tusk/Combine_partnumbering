# Pump Configuration Platform

## Mission
Build a metadata-driven engineering configuration platform that separates engineering knowledge from application code and supports multiple pump families through metadata rather than family-specific runtime logic.

## Core Principles
1. Excel is an engineering metadata source, not a runtime dependency.
2. SQL is the runtime source of truth.
3. The runtime contains no Dean- or Fybroc-specific business logic.
4. Invalid configurations are prevented before identifier generation.
5. The same normalized configuration must always return the same Part Number, SKU, BOM, and price.
6. Every value must be traceable from workbook source through runtime output.

## Current State
- Version: `0.2.0`
- Active milestone: `M009 – Attribute Metadata Platform`
- Pump families: Dean and Fybroc
- Automated tests: 16 passing
- Validated Fybroc segment combinations: 138,403

## Definition of Done
A significant feature is complete only when code, tests, SQL migration, documentation, milestone log, engineering journal, dashboard, and release notes are current.
