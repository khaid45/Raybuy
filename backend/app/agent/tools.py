from decimal import Decimal

from sqlalchemy.orm import Session

from app.catalog import search_catalog
from app.policy import check_spending_policy


def search_catalog_tool(
    db: Session,
    query: str | None = None,
    max_price: float | None = None,
    category: str | None = None,
):
    products = search_catalog(
        db=db,
        query=query,
        max_price=Decimal(str(max_price)) if max_price is not None else None,
        category=category,
    )

    return [
        {
            "id": product.id,
            "merchant_id": product.merchant_id,
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "price": float(product.price),
            "currency": product.currency,
            "metadata": product.metadata_json,
        }
        for product in products
    ]


def check_spending_policy_tool(
    db: Session,
    user_id: int,
    amount: float,
    category: str,
):
    return check_spending_policy(
        db=db,
        user_id=user_id,
        amount=Decimal(str(amount)),
        category=category,
    )