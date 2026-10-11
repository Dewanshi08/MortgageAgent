# own-ly — AI Home Buyer Advisor

**MortgageAgent** is a Canadian mortgage education agent for first-time homebuyers. It collects a buyer's profile, estimates what they can afford under Canadian qualification rules, and answers questions in a chat grounded in a curated mortgage knowledge base.

It is a FastAPI service with a single-file React front end, built to run as a [Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/): data lives in Delta tables queried through a SQL warehouse, and answers come from a Databricks Foundation Model serving endpoint.

> **Status:** MVP, version 0.2.0. Onboarding, affordability, chat and progress tracking work end to end. Agreement analysis is a stub (Phase 2).

## Features

- **Onboarding** — captures income, down payment, target price, location, purchase type and monthly debts (car loan, credit card, student loan, line of credit). The profile can be edited later.
- **Affordability estimate** — maximum mortgage and purchase price under the B-20 stress test, GDS/TDS limits, CMHC insurance and amortization rules.
- **Grounded chat** — each request builds a system prompt from the buyer profile and the knowledge base, then calls the model with the recent conversation.
- **Journey progress** — a five-stage sidebar (Learn, Affordability, Pre-Approval, Shopping, Agreement) that marks topics as covered as they come up in chat.
- **Responsive UI** — collapsible sidebar and a mobile layout below 768px.
- **Mock backend** — an in-memory data layer for local development with no Databricks resources.

## Architecture

```
Browser (React, ui/index.html)
        │  POST /api/context, /api/chat
        ▼
FastAPI (app.py)
        ├── api/affordability.py → qualification math (pure functions)
        ├── api/backend.py       → Delta tables via SQL warehouse, or in-memory mock
        ├── api/knowledge.py     → embedded topics + system prompt builder
        └── ai/llm_client.py     → Databricks Foundation Model API
```

A chat request:

1. Resolves or creates the user and session.
2. Stores the user message.
3. Searches the knowledge base for up to 3 matching topics.
4. Builds the system prompt from all active topics and the buyer profile.
5. Sends the last 10 messages to the serving endpoint.
6. Stores the reply, marks the matched topics as covered, and returns the reply with topics and progress.

## Project structure

```
app.py                  FastAPI entrypoint: routes, lifespan, static UI
app.yaml                Databricks Apps configuration (command + environment)
ai/
  llm_client.py         Foundation Model API client with fallback reply
api/
  affordability.py      Canadian mortgage math (stress test, GDS/TDS, CMHC)
  backend.py            MockBackend and WarehouseBackend
  knowledge.py          Embedded topics + system prompt builder
models/
  model.py              Pydantic request/response schemas
notebooks/
  delta-setup-and-seed.ipynb   Creates the Delta tables and seeds the knowledge base
ui/
  index.html            The React front end (single file, served at /)
  App.js, components/,  Earlier modular copy of the UI — not loaded by index.html
  data/, styles.css
requirements.txt        Dependencies installed by Databricks Apps
pyproject.toml, uv.lock uv project metadata
```

## Local development

Mock mode needs no Databricks workspace:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
USE_MOCK_BACKEND=true python app.py
```

Open <http://localhost:8000>. Interactive API docs are at <http://localhost:8000/docs>. The server runs with auto-reload.

In mock mode:

- Data is held in memory and lost on restart.
- The knowledge base is the 8 topics embedded in `api/knowledge.py`, not the 22 seeded into Delta.
- Chat returns a fallback message unless Databricks credentials are available for the model call. Matched topics and progress are still returned, so the UI is fully exercisable.

To run locally against a workspace instead, authenticate the Databricks CLI (or set `DATABRICKS_HOST` and `DATABRICKS_TOKEN`) and set:

```bash
export DATABRICKS_WAREHOUSE_ID=<warehouse-id>
export MODEL_ENDPOINT=<serving-endpoint-name>
python app.py
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `USE_MOCK_BACKEND` | `false` | `true` uses the in-memory backend instead of the warehouse. |
| `DATABRICKS_WAREHOUSE_ID` | — | SQL warehouse ID. Required unless the mock backend is on. |
| `MODEL_ENDPOINT` | `databricks-gpt-oss-20b` | Serving endpoint to call for chat. |
| `CATALOG` | `workspace` | Unity Catalog catalog holding the tables. |
| `SCHEMA` | `mortgage_agent` | Schema holding the tables. |
| `PORT` | `8000` | Port used by `python app.py`. |

Databricks authentication is resolved by the SDK's `Config()` — automatic inside Databricks Apps, and from your CLI profile or environment locally.

## Databricks setup

### 1. Create the Delta tables

Import `notebooks/delta-setup-and-seed.ipynb` into the workspace and run all cells. It is safe to re-run: tables are created with `IF NOT EXISTS`, the seed is a `MERGE` on `slug`, and a migration cell adds `monthly_debts` to an older `users` table.

| Table | Purpose |
| --- | --- |
| `users` | Buyer profiles (income, down payment, debts, location) |
| `sessions` | Chat sessions per user |
| `messages` | Chat messages; `content` is base64-encoded |
| `knowledge_topics` | 22 mortgage topics across 9 categories |
| `user_progress` | Topics each user has covered |
| `agreements` | Reserved for Phase 2 agreement analysis |

To read messages in SQL:

```sql
SELECT role, cast(unbase64(content) AS STRING) AS content
FROM workspace.mortgage_agent.messages
ORDER BY created_at;
```

For a different catalog or schema, change `CATALOG` and `SCHEMA` at the top of the notebook and set the matching environment variables.

### 2. Deploy the app

1. Create a Databricks App and add two resources whose keys match `app.yaml`:
   - a SQL warehouse with key `sql-warehouse`
   - a serving endpoint with key `serving-endpoint`
2. Grant the app's service principal `USE CATALOG`, `USE SCHEMA`, `SELECT` and `MODIFY` on the schema.
3. Sync the source to the workspace and deploy:

```bash
databricks sync . /Workspace/Users/<you>/ownly
databricks apps deploy ownly --source-code-path /Workspace/Users/<you>/ownly
```

`app.yaml` starts the server with `uvicorn app:app --host 0.0.0.0 --port 8000` and injects the warehouse ID and endpoint name from those resources. See [Known issues](#known-issues) before the first deploy.

## API reference

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Status, version, backend mode and LLM configuration |
| `POST` | `/api/context` | Create or update a buyer profile; returns an affordability estimate |
| `POST` | `/api/chat` | Send a message; returns the reply, matched topics and progress |
| `GET` | `/api/topics` | List active knowledge topics |
| `POST` | `/api/analyze` | Agreement analysis — stub, always returns `pending` |
| `GET` | `/` | Serves the UI |

### `POST /api/context`

All fields are optional. Omit `user_id` to create a new user. A debt counts toward the estimate only when its `has_*` flag is `true`.

```json
{
  "name": "Alex",
  "income": 120000,
  "dp_amount": 80000,
  "target_price": 600000,
  "location": "GTA",
  "province": "ON",
  "is_first_time": true,
  "purchase_type": "resale",
  "liabilities": {
    "has_car_loan": true,
    "car_loan_monthly": 450
  }
}
```

```json
{
  "user_id": "f7f797ba-3f9",
  "status": "saved",
  "affordability_estimate": {
    "estimated_max_mortgage": 460145.0,
    "estimated_max_price": 540145.0,
    "monthly_payment_at_stress": 3350.0,
    "monthly_debts": 450.0,
    "stress_test_rate": 0.0699,
    "gds_ratio": 0.39,
    "tds_ratio": 0.435,
    "limited_by": "GDS ratio",
    "is_insured": true,
    "insurance_premium": 14264.0,
    "amort_years": 25,
    "amort_reason": "25yr (insured, resale)",
    "note": "Rough estimate. Actual qualification depends on full application."
  }
}
```

`affordability_estimate` is `null` unless both `income` and `dp_amount` are provided.

### `POST /api/chat`

`message` is required (1–4000 characters). Pass back `user_id` and `session_id` from earlier responses to continue a conversation.

```json
{
  "user_id": "f7f797ba-3f9",
  "session_id": "f58109a1-78f",
  "message": "How does the stress test affect me?"
}
```

```json
{
  "session_id": "f58109a1-78f",
  "user_id": "f7f797ba-3f9",
  "message": "…",
  "relevant_topics": [
    {
      "id": "st01",
      "title": "Mortgage Stress Test (B-20)",
      "slug": "stress-test-b20",
      "category": "regulatory",
      "difficulty": "beginner"
    },
    {
      "id": "gd01",
      "title": "GDS and TDS Ratios",
      "slug": "gds-tds-ratios",
      "category": "affordability",
      "difficulty": "intermediate"
    }
  ],
  "progress": {
    "topics_covered": 2,
    "topics_total": 8,
    "covered_ids": ["gd01", "st01"],
    "completion_pct": 25.0
  },
  "tokens_used": 812
}
```

## How affordability is calculated

`api/affordability.py` is pure math with no database or API dependencies.

| Rule | Value used |
| --- | --- |
| Qualifying rate | Higher of contract rate + 2% or 5.25%. The contract rate is a fixed 4.99% assumption, giving 6.99%. |
| GDS limit | 39% insured, 35% uninsured |
| TDS limit | 44% insured, 42% uninsured |
| Insured | Down payment under 20% of the estimated price |
| CMHC premium | 4.00% (5–9.99% down), 3.10% (10–14.99%), 2.80% (15–19.99%) |
| Amortization | 30 years for pre-construction and for uninsured mortgages; 25 years for other insured purchases |
| Property tax + heating | Flat monthly estimate by location: GTA $550, Toronto $600, Ottawa $480, Vancouver $500, Calgary $420, otherwise $450 |

The maximum mortgage is the lower of the GDS and TDS results, and `limited_by` reports which one applied. For insured mortgages the amount is scaled down so the payment including the CMHC premium still fits the limit. If income cannot cover tax, heating and debts, the estimate is zero with `limited_by: "insufficient income"`.

These are simplified estimates for education, not a lender's qualification.

## Known issues

- **`app.yaml` is not valid YAML as committed.** Line 4 reads `APP_YAML = """command:` — remove the `APP_YAML = """` prefix before deploying.
- **`requests` is not in `requirements.txt`.** `ai/llm_client.py` imports it, and it arrives only as a dependency of the Databricks packages.
- **`pyproject.toml` is incomplete.** It lists only FastAPI and Uvicorn, so `uv sync` gives an environment that runs mock mode but not the warehouse backend or the model call. It also requires Python 3.14.
- **Warehouse topic search is a whole-message substring match** against title, content and tags, so full-sentence questions often match no topic and progress doesn't advance. The mock backend scores word by word and matches far more readily.
- **SQL is built by string interpolation** with manual quote escaping in `WarehouseBackend`, rather than bound parameters.
- **Sidebar progress is client-side only.** It resets on page reload, and only knowledge topics with an entry in the UI's slug map can mark a sidebar topic.
- **`/api/health` reports `llm: "fallback"`** when `MODEL_ENDPOINT` is unset, although the client still calls the default endpoint.
- **CORS allows all origins**, and the API has no authentication of its own.
- **No automated tests.**

## Roadmap

- Phase 2: purchase agreement (APS) analysis behind `/api/analyze`, using the `agreements` table
- Persist and restore sidebar progress from `user_progress`
- Better topic retrieval than substring matching

## Disclaimer

own-ly provides general educational information about Canadian mortgages. It is not financial or legal advice. Consult a licensed mortgage broker or lawyer before making binding decisions.
