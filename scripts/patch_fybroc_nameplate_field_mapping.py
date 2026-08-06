from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    PROJECT_ROOT
    / "config"
    / "constraint_profiles"
    / "fybroc_series_field_options.json"
)


def main() -> None:
    data = json.loads(
        PROFILE.read_text(encoding="utf-8")
    )
    mapping = data.setdefault(
        "field_code_map",
        {},
    )
    mapping["F_NamePlate"] = "NAMEPLATE_STANDARD"
    mapping["F_NamePlate2"] = "NAMEPLATE"

    PROFILE.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Updated: {PROFILE}")
    print(
        "F_NamePlate  -> NAMEPLATE_STANDARD"
    )
    print(
        "F_NamePlate2 -> NAMEPLATE"
    )


if __name__ == "__main__":
    main()
