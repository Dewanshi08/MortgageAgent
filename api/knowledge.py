"""
own-ly MVP - Knowledge Base & System Prompt Builder

Embedded mortgage topics and system prompt construction.
Topics are loaded into MockBackend at startup and seeded into
Delta tables for WarehouseBackend via a separate notebook.
"""

EMBEDDED_TOPICS = [
    {
        "id": "st01", "category": "regulatory", "title": "Mortgage Stress Test (B-20)",
        "slug": "stress-test-b20",
        "content": "All federally regulated lenders must qualify borrowers at the higher of: "
                   "contract rate + 2% or the BoC benchmark qualifying rate. Applies to new "
                   "mortgages, renewals with a new lender, and refinances.",
        "tags": ["stress test", "b-20", "qualification", "qualifying rate", "osfi"],
        "difficulty": "beginner", "sort_order": 1,
    },
    {
        "id": "dp01", "category": "down_payment", "title": "Down Payment Requirements",
        "slug": "down-payment-requirements",
        "content": "Minimums: 5% on first $500K, 10% on $500K-$1.5M, 20% on $1.5M+. "
                   "Under 20% requires CMHC insurance (2.8-4.0% premium).",
        "tags": ["down payment", "minimum", "5 percent", "20 percent"],
        "difficulty": "beginner", "sort_order": 10,
    },
    {
        "id": "fr01", "category": "rates", "title": "Fixed Rate Mortgages",
        "slug": "fixed-rate",
        "content": "Rate locked for the term. Tied to bond yields. Penalty: greater of "
                   "3 months interest or IRD (can be $15K-$30K+).",
        "tags": ["fixed rate", "bond yield", "ird", "penalty"],
        "difficulty": "beginner", "sort_order": 20,
    },
    {
        "id": "vr01", "category": "rates", "title": "Variable Rate Mortgages",
        "slug": "variable-rate",
        "content": "Fluctuates with prime rate. Quoted as prime +/- X%. Penalty: 3 months "
                   "interest only. Trigger rate risk with fixed-payment variable.",
        "tags": ["variable rate", "prime rate", "trigger rate"],
        "difficulty": "beginner", "sort_order": 21,
    },
    {
        "id": "cc01", "category": "costs", "title": "Closing Costs",
        "slug": "closing-costs",
        "content": "Budget 1.5-4% of purchase price. Includes: land transfer tax, legal fees "
                   "($1.5-2.5K), title insurance ($300-500), home inspection ($400-600).",
        "tags": ["closing costs", "land transfer tax", "legal fees"],
        "difficulty": "beginner", "sort_order": 40,
    },
    {
        "id": "pc01", "category": "pre_construction", "title": "Pre-Construction Risks",
        "slug": "pre-construction-risks",
        "content": "Closing delays (up to 2yr), interim occupancy fees, assignment restrictions, "
                   "price escalation clauses, cancellation rights under Tarion.",
        "tags": ["pre-construction", "builder", "tarion", "assignment"],
        "difficulty": "intermediate", "sort_order": 50,
    },
    {
        "id": "gd01", "category": "affordability", "title": "GDS and TDS Ratios",
        "slug": "gds-tds-ratios",
        "content": "GDS max ~39% (insured) or 35% (uninsured). TDS max ~44% (insured) or 42% "
                   "(uninsured). Calculated at stress test rate, not actual rate.",
        "tags": ["gds", "tds", "debt ratio", "affordability"],
        "difficulty": "intermediate", "sort_order": 30,
    },
    {
        "id": "fh01", "category": "programs", "title": "FHSA + HBP",
        "slug": "fhsa-hbp",
        "content": "FHSA: $8K/yr, $40K lifetime, tax-deductible in, tax-free out. "
                   "HBP: $60K from RRSP tax-free, repay over 15 years. Can combine both.",
        "tags": ["fhsa", "hbp", "first time buyer", "rrsp"],
        "difficulty": "beginner", "sort_order": 70,
    },
]

CATEGORY_LABELS = {
    "regulatory": "REGULATORY FRAMEWORK",
    "down_payment": "DOWN PAYMENT AND INSURANCE",
    "rates": "INTEREST RATES",
    "affordability": "AFFORDABILITY AND RATIOS",
    "costs": "COSTS AND PENALTIES",
    "pre_construction": "PRE-CONSTRUCTION (ONTARIO)",
    "products": "LENDING PRODUCTS",
    "programs": "FIRST-TIME BUYER PROGRAMS",
    "process": "MORTGAGE PROCESS",
}


def build_system_prompt(topics: list[dict], user_profile: dict = None) -> str:
    """Build the full system prompt with knowledge injection."""
    sections: dict[str, list] = {}
    for t in sorted(topics, key=lambda x: x.get("sort_order", 0)):
        cat = t["category"]
        if cat not in sections:
            sections[cat] = []
        sections[cat].append(t)

    lines = [
        "You are own-ly, an AI-powered home buyer advisor for the Canadian market.",
        "You work for the buyer, not the lender. Your goal is to educate, protect, and empower.",
        "Company philosophy: own your dream.",
        "",
    ]

    if user_profile:
        lines.append("=== BUYER PROFILE ===")
        if user_profile.get("name"):
            lines.append(f"Name: {user_profile['name']}")
        if user_profile.get("income"):
            income = user_profile["income"]
            lines.append(f"Annual income: ${income:,.0f}" if isinstance(income, (int, float)) else f"Annual income: {income}")
        if user_profile.get("dp_amount"):
            dp = user_profile["dp_amount"]
            lines.append(f"Down payment: ${dp:,.0f}" if isinstance(dp, (int, float)) else f"Down payment: {dp}")
        if user_profile.get("target_price"):
            tp = user_profile["target_price"]
            lines.append(f"Target price: ${tp:,.0f}" if isinstance(tp, (int, float)) else f"Target price: {tp}")
        if user_profile.get("monthly_debts"):
            md = user_profile["monthly_debts"]
            lines.append(f"Monthly debt obligations: ${md:,.0f}" if isinstance(md, (int, float)) else f"Monthly debts: {md}")
        lines.append(f"Location: {user_profile.get('location', 'GTA')}, {user_profile.get('province', 'ON')}")
        lines.append(f"First-time buyer: {'Yes' if user_profile.get('is_first_time', True) else 'No'}")
        lines.append(f"Purchase type: {user_profile.get('purchase_type', 'pre-construction')}")
        lines.append("")

    lines.append("=== CANADIAN MORTGAGE KNOWLEDGE BASE ===")
    lines.append("")

    for cat, cat_topics in sections.items():
        label = CATEGORY_LABELS.get(cat, cat.upper())
        lines.append(f"--- {label} ---")
        for t in cat_topics:
            lines.append(f"## {t['title']}")
            lines.append(t["content"])
            lines.append("")

    lines.extend([
        "=== RESPONSE GUIDELINES ===",
        "- Use Canadian-specific terminology and rules",
        "- Reference regulations (B-20, B-21, FCAC) when relevant",
        "- Provide concrete dollar amounts and percentages",
        "- Flag risks clearly, especially for pre-construction",
        "- Never quote specific rates (they change daily)",
        "- Recommend consulting a mortgage broker or lawyer for binding decisions",
        "- Track topics discussed and suggest logical next topics",
        "- Keep responses conversational but substantive",
    ])

    return "\n".join(lines)