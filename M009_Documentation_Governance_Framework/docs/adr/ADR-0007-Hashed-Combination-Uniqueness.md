# ADR-0007: Hashed Combination Uniqueness
- Status: Accepted
- Date: 2026-07-16

Readable combination keys are retained, while uniqueness is enforced using a persisted SHA-256 hash to remain within SQL Server index key limits.
