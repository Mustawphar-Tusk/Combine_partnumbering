# Connect FastAPI to PumpConfiguratorDB

## 1. Merge this update into the project

Extract the ZIP into the root of:

`C:\Users\makorede\Downloads\Combine_partnumbering`

Allow the `src` folders to merge.

## 2. Create the environment file

From the project root:

```powershell
Copy-Item .env.example .env -Force
notepad .env
```

For the SQL Server instance used during deployment:

```text
REPOSITORY_BACKEND=sqlserver
SQL_SERVER=localhost
SQL_DATABASE=PumpConfiguratorDB
SQL_DRIVER=ODBC Driver 18 for SQL Server
SQL_TRUSTED_CONNECTION=true
SQL_ENCRYPT=true
SQL_TRUST_SERVER_CERTIFICATE=true
```

Check the installed driver:

```powershell
Get-OdbcDriver |
    Where-Object Name -Like '*SQL Server*' |
    Select-Object Name, Platform
```

## 3. Test SQL directly from Python

```powershell
python -c "from src.database.connection import check_database_connection; print(check_database_connection())"
```

## 4. Run existing tests

```powershell
python -m pytest -q
```

## 5. Start FastAPI

```powershell
python -m uvicorn src.api.main:app --reload
```

Open another PowerShell window, activate the environment, then run:

```powershell
python .\scripts\sql_api_smoke_test.py
```

Expected behavior:

- `/health` reports SQL Server and `PumpConfiguratorDB`.
- First configuration creates a Part Number and SKU.
- Missing pricing returns `0` and `not_found`.
- Second identical request reuses the same identifiers.
