# Pump Configuration Platform

## Current Release

- Version: 0.2.0
- Active milestone: M009 – Attribute Metadata Platform
- Current tests before M009: 16 passing
- Validated Fybroc segment combinations: 138,403

## Mission

Build one metadata-driven configuration platform for Dean, Fybroc, and future pump families.

## Core Rules

- Excel is an engineering source, not runtime.
- SQL is the runtime source of truth.
- No family-specific engineering rules belong in the core engine.
- Invalid selections are prevented before identifier generation.
- Every generated result is traceable to a metadata publication.
