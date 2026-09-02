from decimal import Decimal


from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.agent.service import run_agent
from app.catalog import search_catalog
from app.database import Base, engine, get_db
from app.orders import create_approved_order
from app.payment import create_payment_order
from app.payment import (
    create_payment_order,
    verify_payment,
)


app = FastAPI(
    title="RayBuy API",
    description="AI-powered agentic commerce platform",
    version="0.1.0",
)
# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "raybuy-api",
    }


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar()

    return {
        "status": "ok",
        "database": "raybuy_db",
        "test": value,
    }


# =========================================================
# CATALOG SEARCH
# =========================================================

@app.get("/api/catalog/search")
def catalog_search(
    q: str | None = Query(default=None),
    max_price: Decimal | None = Query(default=None, gt=0),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    products = search_catalog(
        db=db,
        query=q,
        max_price=max_price,
        category=category,
    )

    return {
        "count": len(products),
        "products": [
            {
                "id": product.id,
                "merchant_id": product.merchant_id,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "price": float(product.price),
                "currency": product.currency,
                "available": product.available,
                "metadata": product.metadata_json,
            }
            for product in products
        ],
    }


# =========================================================
# AGENT CHAT
# =========================================================

class AgentRequest(BaseModel):
    message: str


@app.post("/api/agent/chat")
def agent_chat(
    request: AgentRequest,
    db: Session = Depends(get_db),
):
    return run_agent(
        db=db,
        user_message=request.message,
        user_id=2,
    )


# =========================================================
# ORDER CHECK
# =========================================================

class OrderCheckRequest(BaseModel):
    user_id: int = 2
    product_id: int


@app.post("/api/orders/check")
def order_check(
    request: OrderCheckRequest,
    db: Session = Depends(get_db),
):
    """
    Check whether a product can be purchased
    under the user's spending policy.

    This endpoint does NOT create an order.
    """

    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == request.product_id,
            models.Product.available.is_(True),
        )
        .first()
    )

    if product is None:
        return {
            "success": False,
            "message": "Product not found or is unavailable.",
        }

    from app.policy import check_spending_policy

    policy_result = check_spending_policy(
        db=db,
        user_id=request.user_id,
        amount=Decimal(str(product.price)),
        category=product.category,
    )

    return {
        "success": True,
        "product": {
            "id": product.id,
            "name": product.name,
            "price": float(product.price),
            "currency": product.currency,
            "category": product.category,
        },
        "policy": policy_result,
    }


# =========================================================
# ORDER APPROVAL
# =========================================================

class OrderApprovalRequest(BaseModel):
    user_id: int = 2
    product_id: int


@app.post("/api/orders/approve")
def approve_order(
    request: OrderApprovalRequest,
    db: Session = Depends(get_db),
):
    """
    User explicitly approves a purchase.

    The backend re-checks the real product and
    spending policy before creating the order.
    """

    result = create_approved_order(
        db=db,
        user_id=request.user_id,
        product_id=request.product_id,
    )

    return result


# =========================================================
# PAYMENT CREATION
# =========================================================

class PaymentRequest(BaseModel):
    order_id: int


@app.post("/api/payments/create")
def create_payment(
    request: PaymentRequest,
    db: Session = Depends(get_db),
):
    """
    Prepare an existing RayBuy order for payment.

    This currently prepares the order for the
    Razorpay payment layer. No real payment is
    processed by this endpoint yet.
    """

    return create_payment_order(
        db=db,
        order_id=request.order_id,
    )
# =========================================================
# PAYMENT VERIFICATION
# =========================================================

class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@app.post("/api/payments/verify")
def payment_verify(
    request: PaymentVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Verify the Razorpay payment signature and
    mark the RayBuy order as paid.
    """

    return verify_payment(
        db=db,
        razorpay_order_id=request.razorpay_order_id,
        razorpay_payment_id=request.razorpay_payment_id,
        razorpay_signature=request.razorpay_signature,
    )