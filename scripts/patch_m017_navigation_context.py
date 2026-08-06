from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILE = (
    PROJECT_ROOT
    / "src"
    / "configuration_engine"
    / "allowable_navigation.py"
)


def main() -> None:
    text = FILE.read_text(encoding="utf-8")

    old = """current_segment_selections=(
                        segment_selections
                    ),
                )"""

    new = """current_segment_selections=(
                        segment_selections
                    ),
                    current_selections=selections,
                )"""

    if new in text:
        print("Navigation context is already patched.")
        return

    if old not in text:
        raise SystemExit(
            "Expected AvailableOptionsRequest block "
            "was not found."
        )

    FILE.write_text(
        text.replace(old, new),
        encoding="utf-8",
    )

    print(f"Updated: {FILE}")


if __name__ == "__main__":
    main()
