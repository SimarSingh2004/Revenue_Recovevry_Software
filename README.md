# Revenue Recovery Strategy Optimizer

Minimal runtime foundation for the Razorpay AI Buildathon Revenue Recovery project.

## Prerequisites

- Python 3.11 or newer
- Docker Desktop (or Docker Engine with the Compose plugin)

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

## PostgreSQL

Start the local PostgreSQL 16 container:

```powershell
docker compose up -d
```

Stop the container while preserving its named `postgres_data` volume:

```powershell
docker compose down
```

To remove the database data as well, run `docker compose down -v`.

Initialize the database tables and verify the schema:

```powershell
python -m scripts.verify_database
```

Current tables: `recovery_events`, `recovery_cases`, `payment_history`,
`merchant_context`, and `merchant_history`.

Create a recovery event and its initial case:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/recovery-events -ContentType "application/json" -Body '{"event_id":"event_001","event_type":"PAYMENT_FAILED","occurred_at":"2026-08-23T12:00:00Z","payment_id":"payment_001","merchant_id":"merchant_001","customer_id":"customer_001","amount":"125.50","currency":"INR","failure_code":"DECLINED","failure_category":"TEMPORARY_FAILURE","payment_method":"CARD","attempt_number":1}'
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
| `DATABASE_HOST` | `127.0.0.1` | PostgreSQL host exposed by Docker Compose. |
| `DATABASE_PORT` | `5432` | PostgreSQL host port exposed by Docker Compose. |
| `DATABASE_NAME` | `revenue_recovery` | Local PostgreSQL database name. |
| `DATABASE_USER` | `revenue_recovery` | Local PostgreSQL user. |
| `DATABASE_PASSWORD` | `local_development_password` | Local PostgreSQL password. |

Configuration is read from process environment variables and, when present, a local `.env` file. `.env` is intentionally not committed.

PostgreSQL currently provides the database foundation and the five persisted
observable-data tables. No application behavior has been added.

## Recovery action vocabulary

The initial failed-payment slice has a fixed, application-level vocabulary of
recovery interventions. Each action has a canonical intervention cost, which
callers cannot override through the action definition:

| Action | Cost | Basic semantics |
| --- | ---: | --- |
| `RETRY_PAYMENT` | 2 | Re-attempt the current failed payment with the same payment method. A future actual payment attempt increments the payment attempt number. |
| `ALTERNATE_PAYMENT_METHOD` | 3 | Attempt the same outstanding payment with a different available method. A future actual payment attempt increments the payment attempt number. |
| `SEND_PAYMENT_LINK` | 1 | Generate or send a recovery payment link. Sending it does not increment the attempt number; a later customer payment attempt via the link does. |
| `ESCALATE` | 5 | Move the same recovery case to a higher-touch/manual path; it is not a payment attempt. |
| `STOP` | 0 | Deliberately take no recovery intervention for the current case. |

The vocabulary defines only the available interventions, their costs, and their
payment-attempt semantics. Later AI, optimizer, deterministic policy, and
simulator components will consume these definitions to predict, select,
authorize, and execute actions. They—not the vocabulary—will determine
eligibility, expected recovery, or workflow execution.

This stage does not include recovery-event APIs, ingestion, AI, optimization, policy, provider simulation, reconciliation, audit, or evaluation behavior.
