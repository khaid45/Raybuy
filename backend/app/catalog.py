from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


STOP_WORDS = {
    "find",
    "me",
    "the",
    "for",
    "under",
    "with",
    "want",
    "need",
    "best",
    "give",
    "some",
    "please",
    "buy",
    "get",
    "high",
    "protein",
    "meal",
}


def search_catalog(
    db: Session,
    query: str | None = None,
    max_price: Decimal | None = None,
    category: str | None = None,
):
    statement = select(Product).where(
        Product.available.is_(True)
    )

    if max_price is not None:
        statement = statement.where(
            Product.price <= max_price
        )

    if category:
        statement = statement.where(
            Product.category.ilike(category)
        )

    products = db.scalars(statement).all()

    if not query:
        return sorted(
            products,
            key=lambda product: product.price,
        )

    query_lower = query.lower()

    keywords = [
        word.strip().lower()
        for word in query_lower.split()
        if len(word.strip()) > 2
        and word.strip().lower() not in STOP_WORDS
    ]

    def score_product(product: Product):
        score = 0

        name = (product.name or "").lower()
        description = (product.description or "").lower()

        metadata = product.metadata_json or {}

        tags = [
            str(tag).lower()
            for tag in metadata.get("tags", [])
        ]

        dietary = [
            str(item).lower()
            for item in metadata.get("dietary", [])
        ]

        searchable_text = " ".join(
            [
                name,
                description,
                " ".join(tags),
                " ".join(dietary),
            ]
        )

        for keyword in keywords:
            if keyword in name:
                score += 5

            if keyword in description:
                score += 3

            if keyword in tags:
                score += 4

            if keyword in searchable_text:
                score += 1

        # High-protein preference.
        if "protein" in query_lower:
            protein_grams = metadata.get("protein_grams")

            if protein_grams is not None:
                try:
                    protein = float(protein_grams)

                    if protein >= 40:
                        score += 8
                    elif protein >= 30:
                        score += 5
                except (TypeError, ValueError):
                    pass

        # Prefer chicken products for chicken requests.
        if "chicken" in query_lower:
            if "chicken" in name:
                score += 10
            elif "chicken" in description:
                score += 7
            elif "chicken" in tags:
                score += 8

        return score

    scored_products = [
        (product, score_product(product))
        for product in products
    ]

    # Remove products that have absolutely no relevance.
    scored_products = [
        (product, score)
        for product, score in scored_products
        if score > 0
    ]

    # Highest relevance first.
    # Price is used as a tie-breaker.
    scored_products.sort(
        key=lambda item: (
            -item[1],
            item[0].price,
        )
    )

    return [
        product
        for product, score in scored_products
    ]