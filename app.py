import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from models.model import (
    ChatRequest, ChatResponse, ContextRequest, ContextResponse, AnalyzeRequest, AnalyzeResponse, HealthResponse, TopicOut, AgreementStatus
)

from api.backend import get_backend
from api.knowledge import build_system_prompt
from ai.llm_client import get_llm_response

# -- Lifespan --

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize backend on startup."""
    app.state.backend = get_backend()
    use_mock = os.getenv("USE_MOCK_BACKEDN", "true").lower() == "true"
    mock = "MOCK" if use_mock else "LAKEBASE"
    print(f"Mortgage agent MVP started. Backend")
    yield
    print("Mortgage agent MVP stopped.")


app = FastAPI(
    title="Mortgage Agent - AI Home Buyer Advisor",
    version="0.1.0",
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


# -- Health --

@app.get("/api/health", response_model=HealthResponse)
async def health():
    use_mock = os.getenv("USE_MOCK_BACKEND", "true").lower() == "true"
    has_llm = bool(os.getenv("SERVING_ENDPOINT_NAME") or os.getenv("ANTHROPIC_API_KEY"))
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        database="mock" if use_mock else "lakebase",
        llm="configured" if has_llm else "not configured",
    )

# ── Context (User Profile) ──

@app.post("/api/context", response_model=ContextResponse)
async def set_context(req: ContextRequest):
    db = backend()

    uid = req.user_id or str(uuid.uuid4())[:12]
    profile_data = req.model_dump(exclude={"user_id"}, exclude_none=True)

    existing = db.get_user(uid)
    if existing:
        db.update_user(uid, **profile_data)
    else:
        db.create_user(user_id=uid, **profile_data)

    # Calculate basic affordability estimate
    estimate = None
    if req.income and req.dp_amount:
        stress_rate = 0.0725
        max_gds = 0.39
        monthly_income = req.income / 12
        max_monthly_housing = monthly_income * max_gds
        max_mortgage = max_monthly_housing * 12 / stress_rate * (1 - (1 + stress_rate/12)**(-300))
        # Simplified: use basic annuity calc
        est_max_price = min(max_mortgage + req.dp_amount, req.dp_amount / 0.05 if req.dp_amount else 0)
        estimate = {
            "estimated_max_mortgage": round(max_mortgage, 0),
            "estimated_max_price": round(est_max_price, 0),
            "stress_test_rate": stress_rate,
            "note": "This is a rough estimate. Actual qualification depends on full application.",
        }

    return ContextResponse(user_id=uid, affordability_estimate=estimate)

# ── Chat ──

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

# ── Agreement Analysis (Stub) ──

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_agreement(req: AnalyzeRequest):
    """Stub for APS clause analysis. Phase 2 feature."""
    agreement_id = str(uuid.uuid4())[:12]
    return AnalyzeResponse(
        agreement_id=agreement_id,
        status=AgreementStatus.PENDING,
        clauses=[],
        risk_summary={"note": "Agreement analysis is under development. Check back soon."},
    )

# ── Topics listing ──

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

# ── Serve frontend (if ui/ directory exists) ──

if os.path.exists("ui"):
    app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

    @app.get("/")
    async def root():
        return FileResponse("ui/index.html")
else:
    @app.get("/")
    async def root():
        return {"message": "Nope MVP API", "docs": "/docs"}