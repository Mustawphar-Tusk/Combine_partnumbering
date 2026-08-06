# System Architecture

```text
Engineering Workbooks
        |
        v
Workbook Discovery
        |
        v
Metadata Extraction and Compilation
        |
        v
Staging Validation
        |
        v
SQL Metadata Repository
        |
        v
Generic Configuration Engine
        |
        +-- Attribute Resolver
        +-- Combination Resolver
        +-- Constraint Resolver
        +-- Identifier Builder
        +-- BOM Resolver
        +-- Pricing Resolver
        |
        v
FastAPI / Excel / Web UI
```

The runtime interprets approved metadata. It does not execute Excel or contain family-specific engineering rules.
