"""
own-ly MVP - Affordability Calculator

Canadian mortgage qualification math:
  - OSFI B-20 stress test (contract rate + 2% or 5.25%, whichever is higher)
  - GDS ratio: housing costs / gross income (max 39% insured, 35% uninsured)
  - TDS ratio: (housing + debts) / gross income (max 44% insured, 42% uninsured)
  - CMHC insurance tiers for < 20% down payment
  - Property tax + heating estimates by region

This module is pure math with no DB or API dependencies.
"""

from models.model import AffordabilityEstimate


# ═══════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════

# OSFI B-20 stress test: higher of (contract + 2%) or floor
STRESS_TEST_FLOOR = 0.0525
TYPICAL_CONTRACT_RATE = 0.0499  # ~current 5-year fixed ballpark

# GDS/TDS limits
GDS_MAX_INSURED = 0.39
TDS_MAX_INSURED = 0.44
GDS_MAX_UNINSURED = 0.35
TDS_MAX_UNINSURED = 0.42

# Standard amortization
AMORT_YEARS_INSURED = 25
AMORT_YEARS_UNINSURED = 30

# CMHC insurance premium tiers (% of mortgage amount)
# Down payment range -> premium rate
CMHC_TIERS = [
    (0.05, 0.10, 0.0400),  # 5% - 9.99%    -> 4.00%
    (0.10, 0.15, 0.0310),  # 10% - 14.99%   -> 3.10%
    (0.15, 0.20, 0.0280),  # 15% - 19.99%   -> 2.80%
]

# Monthly estimates for property tax + heating (by region, rough)
MONTHLY_TAX_HEATING = {
    "GTA": 550,
    "Toronto": 600,
    "Ottawa": 480,
    "Vancouver": 500,
    "Calgary": 420,
    "default": 450,
}


# ═══════════════════════════════════════════
# Core Math
# ═══════════════════════════════════════════

def get_stress_rate() -> float:
    """B-20 qualifying rate: higher of (contract + 2%) or floor."""
    return max(TYPICAL_CONTRACT_RATE + 0.02, STRESS_TEST_FLOOR)


def monthly_payment(principal: float, annual_rate: float, amort_years: int) -> float:
    """Standard annuity formula for monthly mortgage payment."""
    if principal <= 0 or annual_rate <= 0:
        return 0.0
    r = annual_rate / 12
    n = amort_years * 12
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def get_cmhc_premium_rate(dp_pct: float) -> float:
    """Return CMHC insurance premium rate based on down payment percentage."""
    for low, high, rate in CMHC_TIERS:
        if low <= dp_pct < high:
            return rate
    return 0.0  # 20%+ = no insurance


def get_monthly_tax_heating(location: str) -> float:
    """Estimated monthly property tax + heating by location."""
    return MONTHLY_TAX_HEATING.get(location, MONTHLY_TAX_HEATING["default"])


def determine_amort_years(
    is_insured: bool,
    purchase_type: str = "resale",
    is_first_time: bool = False,
) -> tuple[int, str]:
    """
    Canadian amortization eligibility (as of 2024 federal updates):
      - New construction (pre-construction): 30yr for ALL buyers (insured or not)
      - First-time buyer + 20%+ down (uninsured): 30yr
      - Insured (< 20% down), resale: 25yr max
      - Uninsured (20%+ down), resale, not first-time: 30yr
    Returns (years, reason_string).
    """
    if purchase_type == "pre-construction":
        return 30, "30yr (new construction eligible)"
    if is_insured:
        if is_first_time:
            # Federal update: first-time insured buyers can get 30yr on new builds only
            # For resale insured, still 25yr
            return 25, "25yr (insured, resale)"
        return 25, "25yr (insured)"
    # Uninsured (20%+ down)
    if is_first_time:
        return 30, "30yr (first-time buyer, 20%+ down)"
    return 30, "30yr (uninsured, 20%+ down)"


def calculate_affordability(
    income: float,
    dp_amount: float,
    monthly_debts: float = 0.0,
    location: str = "GTA",
    target_price: float | None = None,
    purchase_type: str = "resale",
    is_first_time: bool = False,
) -> AffordabilityEstimate:
    """
    Calculate maximum affordable home price under Canadian rules.

    Strategy:
      1. Determine stress test rate
      2. First pass: assume insured (< 20% down) to get initial estimate
      3. Determine actual insurance status from dp_pct
      4. Use determine_amort_years() for correct amortization
      5. Apply GDS/TDS with correct limits and amort
      6. Return the binding constraint
    """
    stress_rate = get_stress_rate()
    monthly_income = income / 12
    tax_heat = get_monthly_tax_heating(location)
    r = stress_rate / 12

    # We need to iterate: amort depends on insured status, which depends on price
    # First pass: assume insured to get conservative estimate
    for iteration in range(2):
        if iteration == 0:
            # Conservative first pass: insured assumptions
            gds_max = GDS_MAX_INSURED
            tds_max = TDS_MAX_INSURED
            amort = AMORT_YEARS_INSURED
        else:
            # Second pass: use actual insured/uninsured based on first pass result
            raw_price = max_mortgage + dp_amount
            dp_pct = dp_amount / raw_price if raw_price > 0 else 0
            is_insured = dp_pct < 0.20

            amort, amort_reason = determine_amort_years(is_insured, purchase_type, is_first_time)

            if is_insured:
                gds_max = GDS_MAX_INSURED
                tds_max = TDS_MAX_INSURED
            else:
                gds_max = GDS_MAX_UNINSURED
                tds_max = TDS_MAX_UNINSURED

        n = amort * 12
        annuity_factor = ((1 + r) ** n - 1) / (r * (1 + r) ** n)

        # GDS constraint
        max_payment_gds = monthly_income * gds_max - tax_heat
        if max_payment_gds <= 0:
            return _zero_estimate(stress_rate, monthly_debts)
        max_mortgage_gds = max_payment_gds * annuity_factor

        # TDS constraint
        max_payment_tds = monthly_income * tds_max - tax_heat - monthly_debts
        if max_payment_tds <= 0:
            return _zero_estimate(stress_rate, monthly_debts)
        max_mortgage_tds = max_payment_tds * annuity_factor

        # Binding constraint
        if max_mortgage_gds <= max_mortgage_tds:
            max_mortgage = max_mortgage_gds
            limited_by = "GDS ratio"
            binding_payment = max_payment_gds
        else:
            max_mortgage = max_mortgage_tds
            limited_by = "TDS ratio (debts)"
            binding_payment = max_payment_tds

    # Final insured status
    est_price = max_mortgage + dp_amount
    dp_pct = dp_amount / est_price if est_price > 0 else 0
    is_insured = dp_pct < 0.20
    amort, amort_reason = determine_amort_years(is_insured, purchase_type, is_first_time)

    # CMHC insurance adjustment
    insurance_premium = None
    if is_insured:
        premium_rate = get_cmhc_premium_rate(dp_pct)
        insurance_premium = max_mortgage * premium_rate
        effective_mortgage = max_mortgage + insurance_premium
        actual_payment = monthly_payment(effective_mortgage, stress_rate, amort)
        if actual_payment > binding_payment:
            scale = binding_payment / actual_payment
            max_mortgage *= scale
            insurance_premium = max_mortgage * premium_rate

    est_max_price = max_mortgage + dp_amount
    payment_at_stress = monthly_payment(
        max_mortgage + (insurance_premium or 0),
        stress_rate,
        amort,
    )

    gds_ratio = (payment_at_stress + tax_heat) / monthly_income if monthly_income > 0 else 0
    tds_ratio = (payment_at_stress + tax_heat + monthly_debts) / monthly_income if monthly_income > 0 else 0

    return AffordabilityEstimate(
        estimated_max_mortgage=round(max_mortgage, 0),
        estimated_max_price=round(est_max_price, 0),
        monthly_payment_at_stress=round(payment_at_stress, 0),
        monthly_debts=round(monthly_debts, 0),
        stress_test_rate=stress_rate,
        gds_ratio=round(gds_ratio, 3),
        tds_ratio=round(tds_ratio, 3),
        limited_by=limited_by,
        is_insured=is_insured,
        insurance_premium=round(insurance_premium, 0) if insurance_premium else None,
        amort_years=amort,
        amort_reason=amort_reason,
        note="Rough estimate. Actual qualification depends on full application.",
    )


def _zero_estimate(stress_rate: float, monthly_debts: float) -> AffordabilityEstimate:
    """Return a zero estimate when income is insufficient."""
    return AffordabilityEstimate(
        estimated_max_mortgage=0,
        estimated_max_price=0,
        monthly_payment_at_stress=0,
        monthly_debts=round(monthly_debts, 0),
        stress_test_rate=stress_rate,
        gds_ratio=0,
        tds_ratio=0,
        limited_by="insufficient income",
        is_insured=False,
        note="Income appears insufficient for mortgage qualification at current stress test rates.",
    )