# Revenue Recovery Strategy Optimizer

Minimal runtime foundation for the Razorpay AI Buildathon Revenue Recovery project.

## Prerequisites

- Python 3.11 or newer
- No Docker, database, or external service is required at this stage.

## Local setup

From the repository root, create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Copy the example environment file and adjust values if needed:

```powershell
Copy-Item .env.example .env
```

## Run the application

```powershell
python -m uvicorn app.main:app --reload
```

The service listens on `http://127.0.0.1:8000` by default. Verify it with:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
```

## Current configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Revenue Recovery Strategy Optimizer` | Application name returned by the health check. |
| `APP_ENVIRONMENT` | `development` | Runtime environment label returned by the health check. |

Configuration is read from process environment variables and, when present, a local `.env` file. `.env` is intentionally not committed.

This stage provides application startup and a health endpoint only. It does not include database setup, data models, recovery-event APIs, ingestion, AI, optimization, policy, provider simulation, reconciliation, audit, or evaluation behavior.
