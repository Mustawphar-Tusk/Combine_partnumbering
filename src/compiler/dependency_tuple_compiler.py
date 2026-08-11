from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class DependencyIssue:
    severity: str
    issue_code: str
    message: str
    source_reference: str | None = None


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _norm_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm_compare(value: Any) -> str | None:
    text = _norm_text(value)
    return text.casefold() if text is not None else None


def _label_map(field_reconciliation: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in field_reconciliation:
        canonical = item["canonical_field_code"]
        for label in item.get("labels", []):
            result[str(label).strip().casefold()] = canonical
        result[canonical.casefold()] = canonical
    return result


def _domain_values_by_field(
    reconciliation: dict[str, Any],
    label_to_canonical: dict[str, str],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)

    for domain in reconciliation.get("logic_option_domains", []):
        label = str(domain["field_label"]).strip()
        canonical = label_to_canonical.get(label.casefold())
        if not canonical:
            continue

        headers = domain.get("headers", [])
        for row in domain.get("rows", []):
            # For multi-column domains, every populated cell is retained as a
            # known source value. This is validation only; it does not infer
            # dependency direction or merge columns.
            for header in headers:
                value = _norm_compare(row.get(header))
                if value is not None:
                    result[canonical].add(value)

    return result


def _applicability_values_by_field(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)

    if not path.exists():
        return result

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            field = _norm_text(row.get("field_code"))
            value = _norm_compare(row.get("option_value"))
            if field and value:
                result[field].add(value)

    return result


def _tuple_key(field_codes: list[str], values: list[str | None]) -> str:
    return json.dumps(
        list(zip(field_codes, values)),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def compile_dependency_tuples(
    *,
    project_root: Path,
    profile_path: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    reconciliation_path = _resolve_path(
        project_root,
        profile["reconciliation_json"],
    )
    applicability_path = _resolve_path(
        project_root,
        profile["applicability_ready_csv"],
    )

    reconciliation = json.loads(
        reconciliation_path.read_text(encoding="utf-8")
    )

    if reconciliation.get("summary", {}).get("error_count", 0):
        raise ValueError(
            "M023.1 reconciliation contains errors. "
            "Dependency compilation is blocked."
        )

    label_to_canonical = _label_map(
        reconciliation["field_reconciliation"]
    )
    domain_values = _domain_values_by_field(
        reconciliation,
        label_to_canonical,
    )
    applicability_values = _applicability_values_by_field(
        applicability_path
    )

    identity_fields = set(profile.get("identity_fields", []))
    issues: list[DependencyIssue] = []
    rules: list[dict[str, Any]] = []
    tuples: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []

    rule_status_counts: Counter[str] = Counter()
    tuple_status_counts: Counter[str] = Counter()
    field_usage_counts: Counter[str] = Counter()

    for source in reconciliation["dependencies"]:
        table_name = source["table_name"]
        source_labels = [str(x).strip() for x in source["field_labels"]]

        canonical_fields: list[str] = []
        unknown_labels: list[str] = []

        for label in source_labels:
            canonical = label_to_canonical.get(label.casefold())
            if canonical is None:
                unknown_labels.append(label)
            else:
                canonical_fields.append(canonical)

        if unknown_labels:
            status = "BLOCKED_REVIEW"
            issues.append(
                DependencyIssue(
                    "Error",
                    "DEPENDENCY_FIELD_UNRESOLVED",
                    f"{table_name} contains unresolved field labels: {unknown_labels}.",
                    table_name,
                )
            )
            reviews.append(
                {
                    "review_type": "UNRESOLVED_RULE_FIELDS",
                    "table_name": table_name,
                    "field_labels": source_labels,
                    "unresolved_labels": unknown_labels,
                    "publication_status": status,
                }
            )
            rule_status_counts[status] += 1
            continue

        if len(set(canonical_fields)) != len(canonical_fields):
            status = "BLOCKED_REVIEW"
            issues.append(
                DependencyIssue(
                    "Error",
                    "DEPENDENCY_DUPLICATE_CANONICAL_FIELD",
                    f"{table_name} collapses multiple source columns into the same "
                    f"canonical field: {canonical_fields}.",
                    table_name,
                )
            )
            reviews.append(
                {
                    "review_type": "DUPLICATE_CANONICAL_FIELDS",
                    "table_name": table_name,
                    "field_labels": source_labels,
                    "canonical_fields": canonical_fields,
                    "publication_status": status,
                }
            )
            rule_status_counts[status] += 1
            continue

        unique_rows: dict[str, dict[str, Any]] = {}
        blocked_tuple_count = 0
        duplicate_count = 0
        blank_tuple_count = 0

        for row_index, raw_row in enumerate(source.get("rows", []), start=1):
            values = [_norm_text(raw_row.get(label)) for label in source_labels]

            if all(value is None for value in values):
                continue

            if any(value is None for value in values):
                blank_tuple_count += 1
                blocked_tuple_count += 1
                reviews.append(
                    {
                        "review_type": "BLANK_DEPENDENCY_CELL",
                        "table_name": table_name,
                        "source_row_index": row_index,
                        "field_codes": canonical_fields,
                        "values": values,
                        "publication_status": "BLOCKED_REVIEW",
                    }
                )
                continue

            unknown_values: list[dict[str, str]] = []

            for field_code, value in zip(canonical_fields, values):
                assert value is not None

                if field_code in identity_fields:
                    continue

                compare_value = value.casefold()
                known_domain = domain_values.get(field_code, set())
                known_applicability = applicability_values.get(field_code, set())

                # Accept source values known to either the canonical domain or
                # currently published-ready applicability. This keeps validation
                # conservative while allowing fields that are dependency-only.
                if (
                    compare_value not in known_domain
                    and compare_value not in known_applicability
                ):
                    unknown_values.append(
                        {
                            "field_code": field_code,
                            "value": value,
                        }
                    )

            if unknown_values:
                blocked_tuple_count += 1
                reviews.append(
                    {
                        "review_type": "UNKNOWN_DEPENDENCY_OPTION",
                        "table_name": table_name,
                        "source_row_index": row_index,
                        "unknown_values": unknown_values,
                        "field_codes": canonical_fields,
                        "values": values,
                        "publication_status": "BLOCKED_REVIEW",
                    }
                )
                continue

            key = _tuple_key(canonical_fields, values)

            if key in unique_rows:
                duplicate_count += 1
                continue

            selections = [
                {
                    "field_code": field_code,
                    "field_label": label,
                    "value": value,
                }
                for field_code, label, value in zip(
                    canonical_fields,
                    source_labels,
                    values,
                )
            ]

            unique_rows[key] = {
                "family_code": profile["family_code"].upper(),
                "dependency_version": profile["version"],
                "rule_code": table_name,
                "rule_type": profile["rule_type"],
                "tuple_key": key,
                "field_count": len(canonical_fields),
                "field_codes": canonical_fields,
                "selections": selections,
                "source_table": table_name,
                "source_row_index": row_index,
                "publication_status": "READY",
            }

        rule_status = "READY" if unique_rows else "BLOCKED_REVIEW"

        if not unique_rows:
            issues.append(
                DependencyIssue(
                    "Warning",
                    "DEPENDENCY_RULE_NO_READY_TUPLES",
                    f"{table_name} has no tuples safe for publication.",
                    table_name,
                )
            )

        rule = {
            "family_code": profile["family_code"].upper(),
            "dependency_version": profile["version"],
            "rule_code": table_name,
            "rule_type": profile["rule_type"],
            "source_table": table_name,
            "source_table_range": source.get("table_range"),
            "source_field_labels": source_labels,
            "field_codes": canonical_fields,
            "field_count": len(canonical_fields),
            "source_row_count": source.get("row_count", len(source.get("rows", []))),
            "ready_tuple_count": len(unique_rows),
            "blocked_tuple_count": blocked_tuple_count,
            "duplicate_tuple_count": duplicate_count,
            "blank_tuple_count": blank_tuple_count,
            "publication_status": rule_status,
        }

        rules.append(rule)
        rule_status_counts[rule_status] += 1

        for field_code in canonical_fields:
            field_usage_counts[field_code] += 1

        for item in unique_rows.values():
            tuples.append(item)
            tuple_status_counts[item["publication_status"]] += 1

    errors = sum(1 for x in issues if x.severity == "Error")
    warnings = sum(1 for x in issues if x.severity == "Warning")
    info = sum(1 for x in issues if x.severity == "Info")

    summary = {
        "family_code": profile["family_code"].upper(),
        "dependency_version": profile["version"],
        "source_reconciliation_version": reconciliation.get(
            "reconciliation_version"
        ),
        "workbook_reads": 0,
        "source_dependency_table_count": len(reconciliation["dependencies"]),
        "compiled_rule_count": len(rules),
        "ready_rule_count": sum(
            1 for x in rules if x["publication_status"] == "READY"
        ),
        "blocked_rule_count": sum(
            1 for x in rules if x["publication_status"] != "READY"
        ),
        "ready_tuple_count": len(tuples),
        "review_record_count": len(reviews),
        "rule_status_counts": dict(sorted(rule_status_counts.items())),
        "tuple_status_counts": dict(sorted(tuple_status_counts.items())),
        "field_usage_counts": dict(sorted(field_usage_counts.items())),
        "issue_count": len(issues),
        "error_count": errors,
        "warning_count": warnings,
        "info_count": info,
        "publication_gate": "PASS" if errors == 0 else "FAIL",
        "rule_semantics": (
            "Each Codependencies table is compiled as an undirected allowed-tuple "
            "constraint. No parent/child direction is inferred."
        ),
    }

    return {
        "summary": summary,
        "rules": rules,
        "tuples": tuples,
        "reviews": reviews,
        "issues": [asdict(x) for x in issues],
    }


def project_allowed_values(
    *,
    tuples: Iterable[dict[str, Any]],
    current_selection: dict[str, str],
    target_field: str,
) -> list[str]:
    """
    Generic partial-state projection for an ALLOWED_TUPLES rule.

    A tuple survives when every currently selected field that participates in
    the tuple matches its tuple value. The target field values from surviving
    tuples are returned. No rule direction is assumed.
    """
    normalized_current = {
        str(field): str(value).strip().casefold()
        for field, value in current_selection.items()
        if value is not None
    }

    result: set[str] = set()

    for item in tuples:
        selections = {
            x["field_code"]: str(x["value"]).strip()
            for x in item["selections"]
        }

        if target_field not in selections:
            continue

        compatible = True
        for field, selected_value in normalized_current.items():
            if field not in selections:
                continue
            if selections[field].casefold() != selected_value:
                compatible = False
                break

        if compatible:
            result.add(selections[target_field])

    return sorted(result, key=lambda x: x.casefold())


def _flatten(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields: list[str] = []
    seen: set[str] = set()

    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: _flatten(row.get(key)) for key in fields}
            )


def save_dependency_outputs(
    report: dict[str, Any],
    export_dir: Path,
) -> dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)

    summary = export_dir / "m023_dean_dependency_summary.json"
    rules = export_dir / "m023_dean_dependency_rules.csv"
    tuples = export_dir / "m023_dean_dependency_tuples.csv"
    reviews = export_dir / "m023_dean_dependency_review.csv"
    issues = export_dir / "m023_dean_dependency_issues.csv"

    summary.write_text(
        json.dumps(report["summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_csv(rules, report["rules"])
    _write_csv(tuples, report["tuples"])
    _write_csv(reviews, report["reviews"])
    _write_csv(issues, report["issues"])

    return {
        "summary": summary,
        "rules": rules,
        "tuples": tuples,
        "reviews": reviews,
        "issues": issues,
    }
