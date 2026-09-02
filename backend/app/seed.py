from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Merchant, Product


MERCHANT_NAME = "Protein Kitchen"


PRODUCTS = [
    {
        "name": "Chicken Protein Bowl",
        "description": "Grilled chicken, brown rice, vegetables and high-protein dressing.",
        "category": "food",
        "price": Decimal("349.00"),
        "metadata_json": {
            "protein_grams": 42,
            "calories": 520,
            "serves": 1,
            "prep_time_minutes": 20,
            "dietary": ["non_vegetarian"],
            "tags": ["high_protein", "chicken", "healthy"],
        },
    },
    {
        "name": "Grilled Chicken Meal",
        "description": "Grilled chicken breast with vegetables and seasoned rice.",
        "category": "food",
        "price": Decimal("449.00"),
        "metadata_json": {
            "protein_grams": 55,
            "calories": 610,
            "serves": 1,
            "prep_time_minutes": 25,
            "dietary": ["non_vegetarian"],
            "tags": ["high_protein", "chicken", "grilled"],
        },
    },
    {
        "name": "Paneer Power Bowl",
        "description": "Paneer, quinoa, vegetables and protein-rich dressing.",
        "category": "food",
        "price": Decimal("299.00"),
        "metadata_json": {
            "protein_grams": 28,
            "calories": 490,
            "serves": 1,
            "prep_time_minutes": 18,
            "dietary": ["vegetarian"],
            "tags": ["high_protein", "paneer", "vegetarian"],
        },
    },
    {
        "name": "High Protein Combo",
        "description": "Chicken protein bowl with a protein smoothie.",
        "category": "food",
        "price": Decimal("599.00"),
        "metadata_json": {
            "protein_grams": 68,
            "calories": 720,
            "serves": 1,
            "prep_time_minutes": 25,
            "dietary": ["non_vegetarian"],
            "tags": ["high_protein", "chicken", "combo"],
        },
    },
    {
        "name": "Chicken Tikka Wrap",
        "description": "Whole-wheat wrap filled with chicken tikka and fresh vegetables.",
        "category": "food",
        "price": Decimal("279.00"),
        "metadata_json": {
            "protein_grams": 31,
            "calories": 430,
            "serves": 1,
            "prep_time_minutes": 15,
            "dietary": ["non_vegetarian"],
            "tags": ["protein", "chicken", "wrap"],
        },
    },
    {
        "name": "Protein Smoothie",
        "description": "Milk, banana, peanut butter and whey protein smoothie.",
        "category": "food",
        "price": Decimal("199.00"),
        "metadata_json": {
            "protein_grams": 25,
            "calories": 350,
            "serves": 1,
            "prep_time_minutes": 5,
            "dietary": ["vegetarian"],
            "tags": ["protein", "smoothie"],
        },
    },
]


def seed_catalog():
    db = SessionLocal()

    try:
        merchant = db.scalar(
            select(Merchant).where(Merchant.name == MERCHANT_NAME)
        )

        if merchant is None:
            merchant = Merchant(
                name=MERCHANT_NAME,
                description="Healthy meals and high-protein food for everyday customers.",
                category="food",
                active=True,
            )
            db.add(merchant)
            db.flush()

        existing_products = {
            product.name
            for product in db.scalars(
                select(Product).where(Product.merchant_id == merchant.id)
            ).all()
        }

        added = 0

        for product_data in PRODUCTS:
            if product_data["name"] in existing_products:
                continue

            product = Product(
                merchant_id=merchant.id,
                currency="INR",
                available=True,
                **product_data,
            )

            db.add(product)
            added += 1

        db.commit()

        print(f"Merchant: {merchant.name}")
        print(f"Products added: {added}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_catalog()