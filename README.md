#own-ly - AI Home Buyer Advisor
##MortgageAgent 
Canadian mortgage education agent for first-time homebuyers.

## Local Development

```bash
pip install -r requirements.txt
USE_MOCK_BACKEND=true python app.py
```

Open http://localhost:8000

## Project Structure

```
app.py              # FastAPI entrypoint
ui/index.html       # React frontend (single file)
models/model.py     # Pydantic request/response schemas
api/
  affordability.py  # Canadian mortgage math (GDS/TDS/CMHC)
  backend.py        # Mock + Warehouse data backends
  knowledge.py      # Embedded topics + system prompt
ai/
  llm_client.py     # Databricks Foundation Model API client
```