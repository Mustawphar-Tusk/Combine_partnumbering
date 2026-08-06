from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILE = (
    PROJECT_ROOT
    / "scripts"
    / "test_fybroc_complete_configuration_session.py"
)


STRICT_FUNCTION = """def choose_option(
    response,
    preference: dict[str, str] | None,
):
    if preference is None:
        raise RuntimeError(
            f"No deterministic test preference exists for "
            f"{response.next_field_code}."
        )

    exact = preference.get("exact")
    contains = preference.get("contains")

    for option in response.options:
        if (
            exact is not None
            and option.display_value == exact
        ):
            return option

        if (
            contains is not None
            and contains in option.display_value
        ):
            return option

    raise RuntimeError(
        f"Preferred value was not returned for "
        f"{response.next_field_code}: {preference}. "
        f"Available values: "
        f"{[item.display_value for item in response.options]}"
    )
"""


def main() -> None:
    text = FILE.read_text(encoding="utf-8")
    start = text.index("def choose_option(")
    end = text.index("\n\ndef main()", start)

    FILE.write_text(
        text[:start]
        + STRICT_FUNCTION
        + text[end:],
        encoding="utf-8",
    )

    print(f"Updated: {FILE}")
    print("Silent option fallback removed.")


if __name__ == "__main__":
    main()
