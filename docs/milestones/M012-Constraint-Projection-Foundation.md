# M012 – Constraint Projection Foundation

## Objective

Prevent invalid selections by returning only values that still exist in approved metadata.

## Implemented Projection

### Combination Segments

Given a partial selection set, query the latest validated combination batch and return distinct valid values for the requested next field.

Supported segments:

- PUMP_OPTIONS
- SEAL_ASSEMBLY
- OPTIONS
- MOTOR_ASSEMBLY

### Attribute Segments

Return active attribute values from the current metadata publication.

## Current Boundary

This milestone filters choices inside each combination segment. Cross-segment constraints involving Series, Size, Pump Material, Impeller Trim, and other model-level relationships require compilation from `Fybroc Attributes and Constraints.xlsx`.

The included profiler records worksheet structure and sample rows so that the next compiler is based on authoritative workbook layout rather than assumptions.
