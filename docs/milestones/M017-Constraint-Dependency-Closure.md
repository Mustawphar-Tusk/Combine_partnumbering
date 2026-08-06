# M017 – Constraint Dependency Closure

## Objective

A catalog value is not considered allowable merely because it exists.
Every navigation field must have a declared authoritative projection
policy.

## Impeller Trim

Fybroc Series worksheets contain Series/Size/Trim relationships. The
compiler detects explicit size matrices where present and otherwise
uses the series-level trim list defined in that series worksheet.

Runtime projection becomes:

```text
Active Trim Catalog
∩ Series Applicability
∩ Series+Size Trim Dependency
```

## Motor Modifications

The Smart Number provides three modification selections, not one.
M017 restores:

```text
MOTOR_MODIFICATION_1
MOTOR_MODIFICATION_2
MOTOR_MODIFICATION_3
```

The compiler combines:

- the exact Motor Assembly rows
- vendor support from `NewRules 5-2-23`
- frame classes from `Mod Master List`
- explicit orientation/frame special rules
- modification identifier codes from Nomenclature Attributes

No Motor and unsupported motor states receive only `No Modification`.
Modification slots are ordered, non-duplicating, and terminal after
`No Modification`.

## Testing

Testing remains a reviewed family-global attribute because the
Nomenclature workflow performs a direct lookup against the complete
Testing attribute range and exposes no narrower dependency source.

## Generation Gate

Identifier generation is blocked unless all 41 navigation fields are
present in the dependency coverage policy.

## Deterministic Test

The complete-session test no longer silently chooses the first option.
Every expected value must be explicitly configured and must be returned
by authoritative projection.
