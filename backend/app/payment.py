from decimal import Decimal

import razorpay
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Order, Payment , AuditLog    


# =========================================================
# RAZORPAY CLIENT
# =========================================================

razorpay_client = razorpay.Client(
    auth=(
        settings.razorpay_key_id,
        settings.razorpay_key_secret,
    )
)


# =========================================================
# CREATE RAZORPAY ORDER
# =========================================================

def create_payment_order(
    db: Session,
    order_id: int,
):
    """
    Create a real Razorpay Test Mode order
    for an existing RayBuy order.
    """

    # -----------------------------------------------------
    # 1. FIND RAYBUY ORDER
    # -----------------------------------------------------

    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        return {
            "success": False,
            "message": "Order not found.",
        }

    # -----------------------------------------------------
    # 2. CHECK ORDER STATUS
    # -----------------------------------------------------

    if order.status != "pending":
        return {
            "success": False,
            "message": (
                f"Order cannot enter payment because "
                f"its current status is '{order.status}'."
            ),
        }

    # -----------------------------------------------------
    # 3. PREVENT DUPLICATE RAZORPAY ORDERS
    # -----------------------------------------------------

    if order.razorpay_order_id:
        return {
            "success": True,
            "payment_ready": True,
            "provider": "razorpay",
            "mode": "test",
            "message": "Razorpay order already exists.",
            "order": {
                "id": order.id,
                "amount": float(order.amount),
                "amount_paise": int(
                    Decimal(str(order.amount)) * Decimal("100")
                ),
                "currency": order.currency,
                "status": order.status,
                "razorpay_order_id": order.razorpay_order_id,
                "razorpay_key_id": settings.razorpay_key_id,
            },
        }

    # -----------------------------------------------------
    # 4. CONVERT INR TO PAISE
    # -----------------------------------------------------

    amount = Decimal(str(order.amount))

    amount_in_paise = int(
        amount * Decimal("100")
    )

    # -----------------------------------------------------
    # 5. CREATE RAZORPAY ORDER
    # -----------------------------------------------------

    try:
        razorpay_order = razorpay_client.order.create(
            data={
                "amount": amount_in_paise,
                "currency": order.currency,
                "receipt": f"raybuy_order_{order.id}",
                "notes": {
                    "raybuy_order_id": str(order.id),
                    "user_id": str(order.user_id),
                },
            }
        )

    except Exception as exc:
        return {
            "success": False,
            "message": "Failed to create Razorpay order.",
            "error": str(exc),
        }

    # -----------------------------------------------------
    # 6. SAVE RAZORPAY ORDER ID
    # -----------------------------------------------------

    order.razorpay_order_id = razorpay_order["id"]

    db.commit()
    db.refresh(order)

    # -----------------------------------------------------
    # 7. RETURN CHECKOUT INFORMATION
    # -----------------------------------------------------

    return {
        "success": True,
        "payment_ready": True,
        "provider": "razorpay",
        "mode": "test",
        "message": (
            "Razorpay Test Mode order created successfully."
        ),
        "order": {
            "id": order.id,
            "amount": float(order.amount),
            "amount_paise": amount_in_paise,
            "currency": order.currency,
            "status": order.status,
            "razorpay_order_id": order.razorpay_order_id,
            "razorpay_key_id": settings.razorpay_key_id,
        },
    }


# =========================================================
# VERIFY RAZORPAY PAYMENT
# =========================================================

def verify_payment(
    db: Session,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
):
    """
    Verify a Razorpay payment signature and update
    the corresponding RayBuy order.

    The client/browser cannot directly mark an order
    as paid. The Razorpay signature must be verified
    using the server-side secret.
    """

    # -----------------------------------------------------
    # 1. FIND RAYBUY ORDER
    # -----------------------------------------------------

    order = (
        db.query(Order)
        .filter(
            Order.razorpay_order_id == razorpay_order_id
        )
        .first()
    )

    if order is None:
        return {
            "success": False,
            "message": "RayBuy order not found.",
        }

    # -----------------------------------------------------
    # 2. PREVENT RE-PAYMENT
    # -----------------------------------------------------

    if order.status == "paid":
        return {
            "success": False,
            "message": "This order has already been paid.",
            "order": {
                "id": order.id,
                "status": order.status,
            },
        }

    # -----------------------------------------------------
    # 3. VERIFY RAZORPAY SIGNATURE
    # -----------------------------------------------------

    try:
        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

    except razorpay.errors.SignatureVerificationError:
        return {
            "success": False,
            "message": (
                "Payment verification failed: "
                "invalid Razorpay signature."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "Payment verification failed.",
            "error": str(exc),
        }

    # -----------------------------------------------------
    # 4. PREVENT DUPLICATE PAYMENT RECORD
    # -----------------------------------------------------

    existing_payment = (
        db.query(Payment)
        .filter(
            Payment.razorpay_payment_id
            == razorpay_payment_id
        )
        .first()
    )

    if existing_payment:
        return {
            "success": True,
            "message": "Payment was already recorded.",
            "payment": {
                "id": existing_payment.id,
                "razorpay_payment_id": (
                    existing_payment.razorpay_payment_id
                ),
                "status": existing_payment.status,
                "amount": float(existing_payment.amount),
            },
            "order": {
                "id": order.id,
                "status": order.status,
            },
        }

    # -----------------------------------------------------
    # 5. CREATE PAYMENT RECORD
    # -----------------------------------------------------

    payment = Payment(
        order_id=order.id,
        razorpay_payment_id=razorpay_payment_id,
        amount=order.amount,
        status="paid",
    )

    db.add(payment)

      # -----------------------------------------------------
    # 6. UPDATE RAYBUY ORDER
    # -----------------------------------------------------

    order.status = "paid"

    # Record successful payment in RayBuy audit trail
    audit_log = AuditLog(
        user_id=order.user_id,
        session_id=order.session_id,
        event_type="payment_verified",
        event_data={
            "order_id": order.id,
            "product_id": order.product_id,
            "amount": float(order.amount),
            "currency": order.currency,
            "razorpay_order_id": order.razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "status": "paid",
        },
    )

    db.add(audit_log)

    db.commit()

    db.refresh(payment)
    db.refresh(order)
    # -----------------------------------------------------
    # 7. RETURN SUCCESS
    # -----------------------------------------------------

    return {
        "success": True,
        "message": "Payment verified successfully.",
        "payment": {
            "id": payment.id,
            "razorpay_payment_id": (
                payment.razorpay_payment_id
            ),
            "amount": float(payment.amount),
            "status": payment.status,
        },
        "order": {
            "id": order.id,
            "razorpay_order_id": (
                order.razorpay_order_id
            ),
            "amount": float(order.amount),
            "currency": order.currency,
            "status": order.status,
        },
    }



