"""
own-ly MVP - FastAPI Application
Databricks App entrypoint: uvicorn app:app --host 0.0.0.0 --port 8000
Local dev: USE_MOCK_BACKEND=true python app.py
"""

import os
import uuid
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models.model import (
    ChatRequest, ChatResponse, ContextRequest, ContextResponse,
    AnalyzeRequest, AnalyzeResponse, HealthResponse, TopicOut,
    AgreementStatus, AffordabilityEstimate,
)
from api.backend import get_backend
from api.knowledge import build_system_prompt
from api.affordability import calculate_affordability
from ai.llm_client import get_llm_response


# ═══════════════════════════════════════════
# Lifespan
# ═══════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.backend = get_backend()
    use_mock = os.getenv("USE_MOCK_BACKEND", "false").lower() == "true"
    mode = "MOCK" if use_mock else "SQL_WAREHOUSE"
    print(f"own-ly MVP started. Backend: {mode}")
    yield
    print("own-ly MVP shutting down.")


app = FastAPI(
    title="own-ly - AI Home Buyer Advisor",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def backend():
    return app.state.backend


# ═══════════════════════════════════════════
# Health
# ═══════════════════════════════════════════

@app.get("/api/health", response_model=HealthResponse)
async def health():
    use_mock = os.getenv("USE_MOCK_BACKEND", "false").lower() == "true"
    has_llm = bool(os.getenv("MODEL_ENDPOINT"))
    return HealthResponse(
        status="healthy",
        version="0.2.0",
        database="mock" if use_mock else "sql_warehouse",
        llm="configured" if has_llm else "fallback",
    )


# ═══════════════════════════════════════════
# Context (Onboarding / User Profile)
# ═══════════════════════════════════════════

@app.post("/api/context", response_model=ContextResponse)
async def set_context(req: ContextRequest):
    db = backend()

    uid = req.user_id or str(uuid.uuid4())[:12]

    # Calculate monthly debts from liabilities
    monthly_debts = 0.0
    if req.liabilities:
        monthly_debts = req.liabilities.total_monthly

    # Build profile data (flat dict for DB storage)
    profile_data = {
        "name": req.name,
        "income": req.income,
        "dp_amount": req.dp_amount,
        "location": req.location,
        "province": req.province,
        "is_first_time": req.is_first_time,
        "purchase_type": req.purchase_type,
        "target_price": req.target_price,
        "monthly_debts": monthly_debts,
    }
    # Remove None values
    profile_data = {k: v for k, v in profile_data.items() if v is not None}

    existing = db.get_user(uid)
    if existing:
        db.update_user(uid, **profile_data)
    else:
        db.create_user(user_id=uid, **profile_data)

    # Run affordability calculation if we have income + down payment
    estimate = None
    if req.income and req.dp_amount:
        estimate = calculate_affordability(
            income=req.income,
            dp_amount=req.dp_amount,
            monthly_debts=monthly_debts,
            location=req.location,
            target_price=req.target_price,
            purchase_type=req.purchase_type,
            is_first_time=req.is_first_time,
        )

    return ContextResponse(
        user_id=uid,
        affordability_estimate=estimate,
    )


# ═══════════════════════════════════════════
# Chat
# ═══════════════════════════════════════════

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    db = backend()

    # Resolve or create user
    uid = req.user_id or str(uuid.uuid4())[:12]
    if not db.get_user(uid):
        db.create_user(user_id=uid)

    # Resolve or create session
    sid = req.session_id
    if sid and not db.get_session(sid):
        sid = None
    if not sid:
        sid = db.create_session(uid)

    # Store user message
    db.add_message(sid, "user", req.message)

    # Find relevant knowledge topics
    relevant = db.search_topics(req.message, limit=3)

    # Build conversation history
    history = db.get_messages(sid, limit=10)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    if not any(m["content"] == req.message for m in messages):
        messages.append({"role": "user", "content": req.message})

    # Build system prompt with knowledge + user profile
    all_topics = db.get_all_topics()
    user_profile = db.get_user(uid) or {}
    system_prompt = build_system_prompt(all_topics, user_profile)

    # Get LLM response
    llm_result = get_llm_response(messages, system_prompt)

    # Store assistant response
    db.add_message(sid, "assistant", llm_result["content"], llm_result.get("tokens_used", 0))

    # Update progress for matched topics
    for t in relevant:
        db.mark_topic_covered(uid, t["id"], sid)

    progress = db.get_progress(uid)

    return ChatResponse(
        session_id=sid,
        user_id=uid,
        message=llm_result["content"],
        relevant_topics=[
            TopicOut(
                id=t["id"],
                title=t["title"],
                slug=t["slug"],
                category=t["category"],
                difficulty=t.get("difficulty", "beginner"),
            )
            for t in relevant
        ],
        progress=progress,
        tokens_used=llm_result.get("tokens_used"),
    )


# ═══════════════════════════════════════════
# Agreement Analysis (Phase 2 stub)
# ═══════════════════════════════════════════

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_agreement(req: AnalyzeRequest):
    agreement_id = str(uuid.uuid4())[:12]
    return AnalyzeResponse(
        agreement_id=agreement_id,
        status=AgreementStatus.PENDING,
        clauses=[],
        risk_summary={"note": "Agreement analysis is under development."},
    )


# ═══════════════════════════════════════════
# Topics listing
# ═══════════════════════════════════════════

@app.get("/api/topics")
async def list_topics():
    db = backend()
    topics = db.get_all_topics()
    return {
        "count": len(topics),
        "topics": [
            {
                "id": t["id"],
                "title": t["title"],
                "slug": t["slug"],
                "category": t["category"],
                "difficulty": t.get("difficulty", "beginner"),
            }
            for t in topics
        ],
    }


# ═══════════════════════════════════════════
# Static frontend
# ═══════════════════════════════════════════

if os.path.exists("ui"):
    app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

    @app.get("/")
    async def root():
        return FileResponse("ui/index.html")
else:
    @app.get("/")
    async def root():
        return {"message": "own-ly MVP API", "docs": "/docs"}


# ═══════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)