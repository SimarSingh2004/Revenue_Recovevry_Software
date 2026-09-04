# Recoup

### Revenue Recovery Strategy Optimizer

An AI-powered revenue recovery system that turns failed payments into recovered revenue — Gemini recommends a bounded recovery action, a deterministic policy layer approves, rejects, or forces escalation, an approved action executes in a synthetic payment environment, and every outcome feeds back into a learning memory that improves future decisions.

**AI recommends. Deterministic systems control execution.**

## TL;DR

- A failed payment enters the pipeline → Gemini proposes one action from a bounded set (`RETRY_PAYMENT`, `ALTERNATE_PAYMENT_METHOD`, `SEND_PAYMENT_LINK`, `ESCALATE`, `STOP`) with a predicted recovery probability and rationale.
- The proposal is checked against six deterministic **policy** rules — recovery enabled, action allowed, attempt limit, cooldown, no repeated action, positive expected net value — before anything executes.
- If policy rejects the action, the rejection is fed back to Gemini as `policy_feedback`, and it must choose differently — up to 2 retries per case before the case is forced to `STOPPED`/`ESCALATED`.
- An approved action runs against a synthetic payment simulator; the result is verified and written into `RecoveryLearningMemory`, which also drives a live `/metrics/recovery` endpoint aggregating success rate, recovered value, fee loss, and prediction calibration error across every attempt in the database.
- **Memory works**: giving Gemini three past recovery outcomes for a similar case changed its decision from `RETRY_PAYMENT` (0.80 predicted) to `SEND_PAYMENT_LINK` (0.85 predicted) — see [Evaluation](#evaluation).
- Built with FastAPI + PostgreSQL, React + Vite, Google Gemini for decisioning.

## Screenshots

**Dashboard — recovery metrics and lifecycle at a glance**

![Dashboard overview](docs/screenshots/dashboard.png)

**Failed payment → AI decision — action, predicted probability, rationale**

![Failed payment AI decision](docs/screenshots/ai-recovery-decision.png)

**Policy + execution result — approved action and recovered value**

![Policy and execution result](docs/screenshots/policy-execution.png)

## Evaluation

**Question:** does historical recovery memory actually change what Gemini decides?

**Setup:** the same failed-payment context (a temporary UPI failure) was evaluated twice — once with no historical insights, once with three relevant past outcomes supplied (`app/evaluation/evaluate_memory.py`).

| Metric              | Memory OFF      | Memory ON           |
| ------------------- | --------------- | ------------------- |
| Action              | `RETRY_PAYMENT` | `SEND_PAYMENT_LINK` |
| Predicted recovery  | 0.80            | 0.85                |
| Historical insights | None            | 3                   |

With memory on, Gemini explicitly reasoned from the supplied history:

- `SEND_PAYMENT_LINK` → `SUCCESS` / `POSITIVE_RECOVERY`
- `ALTERNATE_PAYMENT_METHOD` → `FAILED` / `FEE_LOSS`
- `RETRY_PAYMENT` → `FAILED` / `FEE_LOSS`

**Result:** the memory → decision feedback loop works as designed — supplying relevant history measurably changed both the chosen action and the model's confidence.

_Note: the simulator is stochastic and synthetic, so this demonstrates the feedback mechanism, not real-world recovery lift._

**Batch result** — across 75 real recovery attempts:

| Metric                     | Value      |
| -------------------------- | ---------- |
| Successful recoveries      | 40 (53.3%) |
| Total recovered value      | ₹1,28,044  |
| Total fee loss             | ₹69        |
| Net recovered value        | ₹1,27,975  |
| LLM calibration error      | 0.1298     |
| Baseline calibration error | 0.0913     |

The baseline slightly outperforms the LLM on calibration in this batch — expected on a synthetic ground truth this simple, and the reason both are tracked separately rather than assuming the LLM is automatically better.

## Quickstart

### Backend

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
python -m pip install -r requirements.txt
docker compose up -d                # start PostgreSQL
python -m scripts.verify_database
python -m uvicorn app.main:app --reload
```

Backend runs at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Configuration

Copy `.env.example` to `.env` and set:

```env
APP_NAME=Revenue Recovery Strategy Optimizer
APP_ENVIRONMENT=development

DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_NAME=revenue_recovery
DATABASE_USER=revenue_recovery
DATABASE_PASSWORD=local_development_password

GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
```

`VITE_API_BASE_URL` (frontend, optional) defaults to the local backend URL if unset.

### Tests

```bash
python -m pytest
npm run lint
npm run build
```

~100 backend test cases across every service layer, not just a smoke test. Written as Python `unittest.TestCase` classes (run via `pytest` as the runner, not pytest-native fixtures/asserts):

| Layer                                                                           | What's covered                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/services/test_policy_engine.py`                                          | All 6 policy checks individually — recovery disabled, action not allowed, attempt limit reached (and `ESCALATE`/`STOP` still allowed through it), cooldown active/satisfied, duplicate action, zero/negative expected net recovery |
| `tests/services/test_recovery_pipeline.py`                                      | The full retry loop — re-prompting Gemini after a policy rejection, bounded policy retries, successful recovery stopping the cycle, `STOP`/`ESCALATE` not triggering another cycle, repeated rejection resolving the case          |
| `tests/services/test_llm_decision.py`                                           | Gemini decision parsing and service behavior (13 cases)                                                                                                                                                                            |
| `tests/services/test_optimizer.py`                                              | Expected net recovery value calculation                                                                                                                                                                                            |
| `tests/services/test_recovery_memory.py`, `test_recovery_metrics.py`            | Learning memory writes and metrics aggregation                                                                                                                                                                                     |
| `tests/simulator/`                                                              | Payment simulator, ground-truth probability, baseline probability, provider execution                                                                                                                                              |
| `tests/api/test_recovery_events.py`                                             | Event ingestion API — creation, idempotent duplicates, validation errors                                                                                                                                                           |
| `tests/test_recovery_actions.py`, `test_recovery_context.py`, `test_payment.py` | Core enums, context building, payment schema                                                                                                                                                                                       |

This is what backs up the stopping-rule and escalation behavior described below — it's asserted in tests, not just implemented and hoped-for.

## How It Works

```text
Failed Payment
      |
      v
Recovery Context  ───────────────►  Gemini Decision
                                          |
                                          +-- Action, Predicted P(recovery), Rationale
                                          |
                                          v
                                  Economic Evaluation   expected_net_recovery =
                                          |             P(recovery) × amount − action_cost − risk_penalty
                                          v
                                  Policy Evaluation      6 deterministic checks — see below
                                          |
                              rejected ───┴─── approved
                                  │                │
                     fed back to Gemini      Synthetic Execution → SUCCESS / FAILED
                     as policy_feedback,             |
                     retried up to 2×                v
                                  │             Outcome Verification
                                  │                   |
                                  └──► STOPPED /       v
                                       ESCALATED   Learning Memory + Live Metrics
```

Gemini receives a bounded `RecoveryContext`, the recovery actions allowed for that merchant, any relevant historical recovery insights, and — on a retry — the specific policy rejection reasons for the action it just proposed. It must return exactly:

```json
{
  "action": "ALTERNATE_PAYMENT_METHOD",
  "predicted_p_recovery": 0.6,
  "rationale": "The failure context indicates that an alternate payment method is a suitable recovery path."
}
```

### Recovery actions

| Action                     | Purpose                                                          | Cost | Risk penalty |
| -------------------------- | ---------------------------------------------------------------- | ---- | ------------ |
| `RETRY_PAYMENT`            | Retry the failed payment using the existing payment method       | 2    | 1.0          |
| `ALTERNATE_PAYMENT_METHOD` | Attempt recovery through an alternative payment method           | 3    | 1.0          |
| `SEND_PAYMENT_LINK`        | Payment-link style recovery attempt in the synthetic environment | 1    | 0.5          |
| `ESCALATE`                 | Hand the case off instead of continuing automated recovery       | 5    | 2.0          |
| `STOP`                     | Halt recovery on this case — no further attempts                 | 0    | 0.0          |

Gemini is instructed to choose `STOP` or `ESCALATE` once active recovery paths are unviable or exhausted, rather than continuing to force a retry-style action.

### Economic evaluation

```text
expected_net_recovery = predicted_p_recovery × payment_amount − action_cost − risk_penalty
```

An action only reaches policy evaluation with a real expected-value number attached; `STOP` always evaluates to 0.

### Policy evaluation — the six deterministic checks

Every proposed action must pass all of the following before it can execute:

1. **Recovery enabled** — the merchant has recovery turned on.
2. **Action allowed** — the action is in that merchant's `allowed_recovery_actions`.
3. **Attempt limit satisfied** — `recovery_attempt_count < max_recovery_attempts` (unless the action itself is `ESCALATE` or `STOP`, which are always permitted through this check).
4. **Cooldown satisfied** — enough time has passed since the last recovery attempt (`retry_cooldown_seconds`), for retry-style actions only.
5. **No duplicate action** — the same action can't be attempted twice in a row on the same case.
6. **Positive expected net recovery** — expected_net_recovery > 0. STOP and ESCALATE are exempt from this check: they represent a deliberate decision not to attempt recovery, not a failed attempt, so gating them on positive recovery value would make them permanently unreachable.

If any check fails, the action is rejected with an explicit reason (e.g. _"Maximum recovery attempts (3) reached"_, _"Cooldown period is still active"_). The rejection is appended to `policy_feedback` and passed back to Gemini, which is instructed to treat it as a hard constraint and choose a different action. This retry loop runs up to **2 additional times per case**; if no action is approved after that, the case is force-resolved as `STOPPED` (Gemini chose `STOP`) or `ESCALATED` (Gemini chose `ESCALATE`) — the stopping rule that prevents indefinite retries on an unrecoverable case.

### Stopping rules & escalation — case resolution

A recovery case ends in exactly one of three states, all recorded on the case and in `RecoveryLearningMemory`:

- **`RECOVERED`** — the executed action returned `SUCCESS`.
- **`STOPPED`** — Gemini (correctly) determined no further attempt is worth making, or the attempt limit was reached and `STOP` was the resolved path.
- **`ESCALATED`** — Gemini determined the case needs handling outside the automated loop.

This is the compliant-escalation and stopping-rule behavior end to end: bounded retries, explicit reasons at every rejection, and a guaranteed terminal state instead of infinite looping.

### Learning memory & audit trail

Every completed attempt is written to `RecoveryLearningMemory` with the action taken, Gemini's predicted probability, the ground-truth outcome probability, a baseline probability, the failure category, payment method, financial impact (`POSITIVE_RECOVERY` / `FEE_LOSS`), and attempt number — plus a parallel `MerchantHistory` row (action, outcome, amount, intervention cost, timestamp) per merchant. Together these give a full, queryable trail of what was recommended, what was allowed, what ran, and what it cost or recovered.

## Live Recovery Metrics — `GET /metrics/recovery`

Computed directly from the database across every case processed, not from a single sample:

- **Recovery success rate** = successful recoveries ÷ total recovery attempts (`STOPPED`/`ESCALATED` cases excluded from the denominator)
- **Total recovered value** — sum of `net_recovery_value` where `financial_impact = POSITIVE_RECOVERY`
- **Total fee loss** — sum of `net_recovery_value` where `financial_impact = FEE_LOSS`
- **Net recovered value** — recovered value minus fee loss, across all outcomes
- **LLM probability error** — mean(|predicted − ground truth|) across every scored attempt
- **Baseline probability error** — the same calibration metric for a non-LLM baseline, for direct comparison

## Project Structure

```text
Revenue_Recovevry_Software/
|
+-- app/
|   +-- api/            payments.py, recovery_events.py, metrics.py
|   +-- core/           config.py, model_check.py, recovery_actions.py
|   +-- db/             session.py
|   +-- evaluation/     evaluate_memory.py
|   +-- models/         base.py, recovery.py
|   +-- schemas/        llm_decision.py, payment.py, policy_decision.py,
|   |                   recovery_context.py, recovery_event.py, recovery_memory.py
|   +-- services/       llm_decision.py, optimizer.py, policy_engine.py,
|   |                   recovery_context.py, recovery_dashboard.py, recovery_event.py,
|   |                   recovery_memory.py, recovery_metrics.py, recovery_pipeline.py
|   +-- simulator/      baseline.py, ground_truth.py, payment_provider.py, payments.py
|   +-- main.py
|
+-- frontend/
|   +-- src/App.jsx
|   +-- package.json
|   +-- vite.config.js
|
+-- docs/
|   +-- evaluation_memory.md
|   +-- screenshots/    dashboard.png, ai-recovery-decision.png, policy-execution.png
|
+-- scripts/            verify_database.py
+-- tests/
+-- docker-compose.yml
+-- requirements.txt
+-- .env.example
```

## Tech Stack

| Layer          | Stack                                                      |
| -------------- | ---------------------------------------------------------- |
| Backend        | Python, FastAPI, SQLAlchemy, PostgreSQL, Pydantic, Psycopg |
| AI             | Google Gemini (`google-genai`)                             |
| Frontend       | React, Vite, JavaScript, ESLint                            |
| Infrastructure | Docker Compose, PostgreSQL                                 |
| Testing        | Pytest, ESLint, Vite production build                      |

## Design Principles

- **AI recommends, systems decide.** Gemini never executes a payment or overrides policy — every recommendation passes through economic and policy gates, with rejections fed back to the model as hard constraints.
- **Bounded action space.** Gemini can only choose from the recovery actions a merchant explicitly permits.
- **Guaranteed termination.** Every case resolves to `RECOVERED`, `STOPPED`, or `ESCALATED` — no case can retry indefinitely.
- **Synthetic, not live.** The payment execution layer is a simulator, kept deliberately separate from real payment infrastructure.
- **Measurable by design.** Every attempt is verified and logged, so predicted probability can be checked against ground truth and a baseline, live, across the full batch.

## Demo Flow

1. Create a payment (₹1,000, CARD, outcome `SUCCESS`) — it succeeds and never enters recovery.
2. Create another (₹1,000, CARD, outcome `FAILED`) — it enters the recovery pipeline.
3. Gemini returns an action, predicted recovery probability, and rationale.
4. The action runs through the six policy checks; a rejection is shown with its reason and triggers a retry with `policy_feedback`.
5. An approved action runs through the synthetic simulator and returns `SUCCESS` or `FAILED`; repeated failure resolves the case to `STOPPED` or `ESCALATED`.
6. `GET /metrics/recovery` updates recovered value, fee loss, net recovered value, success rate, and calibration error across the full batch.

This is a deliberately scoped vertical slice — failed payments as the initial recovery domain — built to show the full loop from AI recommendation to economic control, policy control, bounded retries, safe execution, verification, and measurable financial outcome.
