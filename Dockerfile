# FastAPI backend for the Pump Configurator.
#
# This image bakes in the Microsoft ODBC Driver 18 for SQL Server, which pyodbc
# requires at the system level (this is why the backend runs on Render/Docker
# and NOT on Vercel's serverless Python runtime). It connects to SQL Server via
# the DB_* environment variables (see DEPLOYMENT.md), typically an ngrok TCP
# tunnel to a local SQL Server for the test environment.
FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# --- System deps + Microsoft ODBC Driver 18 (Debian 12 / bookworm) ---
# Reference: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates apt-transport-https unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
        | tee /etc/apt/sources.list.d/mssql-release.list \
    && sed -i 's#deb https://#deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://#' \
        /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python dependencies (copy requirements first for layer caching) ---
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

# --- Application code ---
# .dockerignore keeps workbooks, .venv, .env, and other non-runtime files out.
COPY . .

# Render/other PaaS inject the listen port via $PORT; default to 8080 locally.
ENV PORT=8080
EXPOSE 8080

# Shell form so ${PORT} is expanded at runtime.
CMD uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT}
