# ADR-0011: Use Numeric Motor Frame Stem for Cross-Source Matching

- Status: Accepted
- Date: 2026-08-04

## Context

The Fybroc series matrix stores `JM` frame names while the Motor Assembly table stores a numeric frame and separate orientation.

## Decision

Normalize Motor Frame to its leading numeric stem for intersections across metadata sources.

## Consequences

- Series applicability filters valid numeric frame sizes.
- Motor Assembly combination metadata continues to validate orientation and all other motor attributes.
- No suffix is invented during runtime comparison.
