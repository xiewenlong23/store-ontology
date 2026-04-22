"""
Discount Tier Constants — Shared fallback rules for clearance discount.

⚠️ SYNC WARNING: These values must stay in sync with WORKTASK-MODULE.ttl
When modifying, always update both places together.
"""

# (min_rate, max_rate, recommended_rate)
DISCOUNT_TIERS = {
    1: (0.10, 0.50, 0.20),   # T1: 0-1 days  -> 10-50%, rec 20%
    2: (0.30, 0.60, 0.40),   # T2: 2-3 days  -> 30-60%, rec 40%
    3: (0.50, 0.80, 0.70),   # T3: 4-7 days  -> 50-80%, rec 70%
    4: (0.70, 0.90, 0.85),   # T4: 8-14 days -> 70-90%, rec 85%
    5: (0.90, 1.00, 0.95),   # T5: 15-30 days -> 90-100%, rec 95%
}


def get_fallback_tier(days_left: int) -> tuple[int, float, list[float]]:
    """
    Return fallback tier for given remaining shelf life days.

    Returns:
        (tier_number, recommended_discount, [min_rate, max_rate])
    """
    if days_left <= 1:
        return 1, 0.20, [0.10, 0.50]
    if days_left <= 3:
        return 2, 0.40, [0.30, 0.60]
    if days_left <= 7:
        return 3, 0.70, [0.50, 0.80]
    if days_left <= 14:
        return 4, 0.85, [0.70, 0.90]
    return 5, 0.95, [0.90, 1.00]