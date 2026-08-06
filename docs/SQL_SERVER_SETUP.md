# SQL Server setup — Phase 1

Run all commands from the project root while `.venv` is active.

## 1. Install the updated dependency

```powershell
pip install -r requirements.txt
```

## 2. Create `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

For a local default SQL Server instance with Windows authentication:

```text
REPOSITORY_BACKEND=sqlserver
SQL_SERVER=localhost
SQL_DATABASE=PumpConfiguratorDB
SQL_DRIVER=ODBC Driver 18 for SQL Server
SQL_TRUSTED_CONNECTION=true
SQL_ENCRYPT=true
SQL_TRUST_SERVER_CERTIFICATE=true
```

For SQL Server Express, the server is commonly:

```text
SQL_SERVER=localhost\SQLEXPRESS
```

## 3. Confirm the ODBC driver

```powershell
Get-OdbcDriver | Where-Object Name -Like '*SQL Server*' | Select-Object Name, Platform
```

The `.env` driver text must exactly match an installed driver.

## 4. Apply the SQL scripts

These scripts assume `PumpConfiguratorDB` already exists and that your account can create schemas and objects inside it.

```powershell
sqlcmd -S localhost -d PumpConfiguratorDB -E -C -b -i .\sql\01_phase1_dynamic_schema.sql
sqlcmd -S localhost -d PumpConfiguratorDB -E -C -b -i .\sql\02_phase1_dynamic_procedures.sql
sqlcmd -S localhost -d PumpConfiguratorDB -E -C -b -i .\sql\03_phase1_seed_development.sql
```

For a named instance, replace `localhost` with, for example, `localhost\SQLEXPRESS`.

`-E` uses Windows authentication, `-C` trusts the server certificate, and `-b` returns an error code when a script fails.

## 5. Test the database connection

```powershell
python -c "from src.database.connection import check_database_connection; print(check_database_connection())"
```

Expected shape:

```text
{'status': 'ok', 'server': '...', 'database': 'PumpConfiguratorDB'}
```

## 6. Run unit tests

```powershell
python -m pytest -q
```

Expected:

```text
3 passed
```

## 7. Start FastAPI

```powershell
python -m uvicorn src.api.main:app --reload
```

Open the API documentation at:

```text
http://127.0.0.1:8000/docs
```

The `/health` endpoint now verifies the SQL Server connection when `REPOSITORY_BACKEND=sqlserver`.

## Current development seed

The seed script creates published version 1 records for Dean and Fybroc only. Actual fields, options, hex codes, constraints, pricing, and quote mappings will be loaded by the workbook metadata compiler in the next stage.
