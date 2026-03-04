from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class AgreementStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    ERROR = "error"

# ── Request Models ──

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=4000)

class ContextRequest(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = None
    income: Optional[float] = None
    dp_amount: Optional[float] = None
    location: str = "GTA"
    province: str = "ON"
    is_first_time: bool = True
    purchase_type: str = "pre-construction"
    target_price: Optional[float] = None

class AnalyzeRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    filename: str
    context_text: str = Field(..., min_length=10)

# -- Response Models --

class TopicOut(BaseModel):
    id: str
    title: str
    slug: str
    category: str
    difficulty: str

class ChatResponse(BaseModel):
    session_id: str
    user_id: str
    message: str
    relevant_topics: list[TopicOut] = []
    progress: dict = {}
    tokens_used: Optional[int] = None

class ContextResponse(BaseModel):
    user_id: str
    status: str = "saved"
    affordability_estimate: Optional[dict] = None

class AnalyzeResponse(BaseModel):
    agreement_id: str
    status: AgreementStatus
    clauses: list[dict] = []
    risk_summary: dict = {}

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    llm: str

# ── Internal Models ──

class UserProfile(BaseModel):
    id: str
    name: Optional[str] = None
    income: Optional[float] = None
    dp_amount: Optional[float] = None
    location: str = "GTA"
    province: str = "ON"
    is_first_time: bool = True
    purchase_type: str = "pre-construction"
    target_price: Optional[float] = None


class KnowledgeTopic(BaseModel):
    id: str
    category: str
    title: str
    slug: str
    content: str
    tags: list[str] = []
    difficulty: Difficulty = Difficulty.BEGINNER
    sort_order: int = 0