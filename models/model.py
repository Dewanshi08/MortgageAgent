"""
own-ly MVP - Pydantic Models
Request/response schemas and internal domain models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════

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


class PurchaseType(str, Enum):
    PRE_CONSTRUCTION = "pre-construction"
    RESALE = "resale"
    REFINANCE = "refinance"


# ═══════════════════════════════════════════
# Nested / Shared Models
# ═══════════════════════════════════════════

class Liabilities(BaseModel):
    """Monthly debt obligations for TDS calculation."""
    has_car_loan: bool = False
    car_loan_monthly: Optional[float] = None
    has_credit_card: bool = False
    credit_card_monthly: Optional[float] = None
    has_student_loan: bool = False
    student_loan_monthly: Optional[float] = None
    has_loc: bool = False
    loc_monthly: Optional[float] = None

    @property
    def total_monthly(self) -> float:
        total = 0.0
        if self.has_car_loan and self.car_loan_monthly:
            total += self.car_loan_monthly
        if self.has_credit_card and self.credit_card_monthly:
            total += self.credit_card_monthly
        if self.has_student_loan and self.student_loan_monthly:
            total += self.student_loan_monthly
        if self.has_loc and self.loc_monthly:
            total += self.loc_monthly
        return total


class AffordabilityEstimate(BaseModel):
    """Returned from /context when income + dp are provided."""
    estimated_max_mortgage: float
    estimated_max_price: float
    monthly_payment_at_stress: float
    monthly_debts: float = 0.0
    stress_test_rate: float
    gds_ratio: float
    tds_ratio: float
    limited_by: str
    is_insured: bool
    insurance_premium: Optional[float] = None
    amort_years: int = 25
    amort_reason: str = ""
    note: str = "Rough estimate. Actual qualification depends on full application."


# ═══════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════

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
    liabilities: Optional[Liabilities] = None


class AnalyzeRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    filename: str
    context_text: str = Field(..., min_length=10)


# ═══════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════

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
    affordability_estimate: Optional[AffordabilityEstimate] = None


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


# ═══════════════════════════════════════════
# Internal Domain Models
# ═══════════════════════════════════════════

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
    monthly_debts: float = 0.0


class KnowledgeTopic(BaseModel):
    id: str
    category: str
    title: str
    slug: str
    content: str
    tags: list[str] = []
    difficulty: Difficulty = Difficulty.BEGINNER
    sort_order: int = 0