from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PATH = (
    ROOT
    / "config"
    / "runtime_profiles"
    / "fybroc_value_equivalences.json"
)

TARGET_CANONICAL_KEY = (
    "NO_SEAL_NO_GLAND"
)

CORRECT_RUNTIME_VALUE = (
    "No Seal (No Seal Gland)"
)


def visit(node) -> int:
    updated = 0

    if isinstance(
        node,
        dict,
    ):
        if (
            node.get("canonical_key")
            == TARGET_CANONICAL_KEY
            and isinstance(
                node.get("values"),
                list,
            )
        ):
            values = node["values"]

            if (
                CORRECT_RUNTIME_VALUE
                not in values
            ):
                values.append(
                    CORRECT_RUNTIME_VALUE
                )
                updated += 1

        for value in node.values():
            updated += visit(
                value
            )

    elif isinstance(
        node,
        list,
    ):
        for value in node:
            updated += visit(
                value
            )

    return updated


def main() -> None:
    data = json.loads(
        PATH.read_text(
            encoding="utf-8-sig",
        )
    )

    updated = visit(
        data
    )

    if updated:
        PATH.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        "NO_SEAL_NO_GLAND aliases added:",
        updated,
    )
    print(
        "Preserved legacy alias:",
        "No Seal (No SealGland)",
    )
    print(
        "Ensured runtime alias:",
        CORRECT_RUNTIME_VALUE,
    )


if __name__ == "__main__":
    main()
