from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Order, SpendingPolicy


def check_spending_policy(
    db: Session,
    user_id: int,
    amount: Decimal,
    category: str,
):
    policy = (
        db.query(SpendingPolicy)
        .filter(SpendingPolicy.user_id == user_id)
        .first()
    )

    if policy is None:
        return {
            "allowed": False,
            "requires_approval": False,
            "reason": "No spending policy is configured for this user.",
        }

    # 1. Check transaction limit
    if amount > policy.max_transaction_amount:
        return {
            "allowed": False,
            "requires_approval": False,
            "reason": (
                f"Amount ₹{amount} exceeds the maximum transaction "
                f"limit of ₹{policy.max_transaction_amount}."
            ),
        }

    # 2. Check category
    allowed_categories = policy.allowed_categories or []

    if allowed_categories and category.lower() not in [
        str(item).lower() for item in allowed_categories
    ]:
        return {
            "allowed": False,
            "requires_approval": False,
            "reason": (
                f"Category '{category}' is not allowed by "
                "the user's spending policy."
            ),
        }

    # 3. Calculate today's spending
    today_spending = (
        db.query(func.coalesce(func.sum(Order.amount), 0))
        .filter(
            Order.user_id == user_id,
            func.date(Order.created_at) == func.current_date(),
            Order.status.in_(["created", "paid", "completed"]),
        )
        .scalar()
    )

    today_spending = Decimal(str(today_spending or 0))

    remaining_daily_limit = (
        policy.daily_limit - today_spending
    )

    # 4. Check daily limit
    if today_spending + amount > policy.daily_limit:
        return {
            "allowed": False,
            "requires_approval": False,
            "reason": (
                f"Purchase would exceed today's spending limit of "
                f"₹{policy.daily_limit}. "
                f"Already spent today: ₹{today_spending}."
            ),
            "daily_limit": float(policy.daily_limit),
            "spent_today": float(today_spending),
            "remaining_today": float(max(remaining_daily_limit, 0)),
        }

    # 5. Everything is within bounds
    return {
        "allowed": True,
        "requires_approval": policy.approval_required,
        "reason": (
            "Purchase is within the transaction and daily "
            "spending limits."
        ),
        "amount": float(amount),
        "transaction_limit": float(
            policy.max_transaction_amount
        ),
        "daily_limit": float(policy.daily_limit),
        "spent_today": float(today_spending),
        "remaining_today": float(
            remaining_daily_limit - amount
        ),
        "category": category,
    }