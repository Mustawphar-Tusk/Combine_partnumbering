from pathlib import Path

required = [
    "src/api/main.py",
    "src/config/settings.py",
    "src/database/connection.py",
    "src/repositories/sql_repository.py",
    "src/services/configured_product_service.py",
]

missing = [path for path in required if not Path(path).exists()]

if missing:
    raise SystemExit("Missing files:\n" + "\n".join(missing))

print("Project structure verified.")
