from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Order, Product
from app.policy import check_spending_policy


def create_approved_order(
    db: Session,
    user_id: int,
    product_id: int,
):
    # -----------------------------------------------------
    # 1. Fetch the REAL product
    # -----------------------------------------------------

    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.available.is_(True),
        )
        .first()
    )

    if product is None:
        return {
            "success": False,
            "message": "Product not found or is unavailable.",
        }

    # -----------------------------------------------------
    # 2. Use the REAL database price
    # -----------------------------------------------------

    amount = Decimal(str(product.price))

    # -----------------------------------------------------
    # 3. Re-check spending policy
    #
    # This is mandatory even after user approval.
    # -----------------------------------------------------

    policy_result = check_spending_policy(
        db=db,
        user_id=user_id,
        amount=amount,
        category=product.category,
    )

    # -----------------------------------------------------
    # 4. Policy rejection
    # -----------------------------------------------------

    if not policy_result["allowed"]:
        return {
            "success": False,
            "message": "Purchase rejected by spending policy.",
            "product": {
                "id": product.id,
                "name": product.name,
                "price": float(product.price),
                "currency": product.currency,
            },
            "policy": policy_result,
        }

    # -----------------------------------------------------
    # 5. User has explicitly approved the purchase.
    #
    # Therefore approval_required=True is NOT a blocker
    # here. This endpoint represents that approval.
    # -----------------------------------------------------

    # -----------------------------------------------------
    # 6. Create internal order
    # -----------------------------------------------------

    order = Order(
        user_id=user_id,
        product_id=product.id,
        merchant_id=product.merchant_id,
        amount=amount,
        currency=product.currency,
        status="pending",
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    # -----------------------------------------------------
    # 7. Return order information
    # -----------------------------------------------------

    return {
        "success": True,
        "message": "Purchase approved and order created.",
        "order": {
            "id": order.id,
            "user_id": order.user_id,
            "product_id": order.product_id,
            "product_name": product.name,
            "merchant_id": order.merchant_id,
            "amount": float(order.amount),
            "currency": order.currency,
            "status": order.status,
        },
        "policy": policy_result,
    }