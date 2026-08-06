# M015 – Allowable Configuration Navigation

## Objective

Navigate only through choices that exist in authoritative allowable
configuration metadata.

## User-Facing Model

The client never submits an engineering value directly.

The service issues:

```text
Signed state token
Signed option tokens for the next field
```

The client returns one issued option token. The service then projects
the next allowable option set.

## Runtime Flow

```text
Start family
→ issue allowable Series tokens
→ select one issued Series token
→ issue allowable Size tokens
→ select one issued Size token
→ issue allowable Material tokens
→ continue until complete
→ generate identifiers
```

## Defensive Integrity

Tokens are bound to:

- pump family
- metadata runtime revision
- exact configuration state
- expected next field

An option from another state, family, field, or metadata revision is
rejected internally. This is not a user-facing invalid-selection
workflow; it protects the authoritative navigation boundary.
