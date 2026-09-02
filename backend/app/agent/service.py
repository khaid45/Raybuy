from decimal import Decimal

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.agent.tools import search_catalog_tool
from app.config import settings
from app.policy import check_spending_policy


# =========================================================
# GEMINI CLIENT
# =========================================================

client = genai.Client(
    api_key=settings.gemini_api_key
)

MODEL = "gemini-3.6-flash"


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are RayBuy, an AI commerce buyer.

Your job is to help users discover products and safely
prepare purchases.

Rules:

1. Never invent products, prices, availability, or
   product attributes.

2. Use the search_catalog tool whenever the user asks
   about products.

3. Base recommendations only on products returned by
   the search_catalog tool.

4. Respect the user's budget and requirements.

5. Do not infer unavailable nutritional or product
   attributes.

6. If a requested attribute is not present in the
   catalog data, say that the information is unavailable.

7. If a purchase is being considered, explain the
   spending-policy result.

8. If approval is required, clearly ask the user for
   approval.

9. Never bypass or override the spending policy.

10. Do not create orders or make payments from this
    agent endpoint.

11. Do not claim that an order or payment was completed.

12. If no suitable product exists, say so honestly.
"""


# =========================================================
# SEARCH CATALOG TOOL DECLARATION
# =========================================================

search_catalog_declaration = types.FunctionDeclaration(
    name="search_catalog",
    description=(
        "Search the merchant catalog for available "
        "products matching the user's requirements."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description=(
                    "Keywords describing the product "
                    "the user wants."
                ),
            ),
            "max_price": types.Schema(
                type=types.Type.NUMBER,
                description=(
                    "Maximum acceptable price in INR."
                ),
            ),
            "category": types.Schema(
                type=types.Type.STRING,
                description="Product category.",
            ),
        },
    ),
)


search_catalog_tool_config = types.Tool(
    function_declarations=[
        search_catalog_declaration
    ]
)


# =========================================================
# AGENT
# =========================================================

def run_agent(
    db: Session,
    user_message: str,
    user_id: int = 2,
):
    """
    Run the RayBuy AI agent.

    The agent can search the real catalog and evaluate
    the spending policy.

    It does NOT create orders or process payments.
    """

    # =====================================================
    # FIRST GEMINI TURN
    # =====================================================

    response = client.models.generate_content(
        model=MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[search_catalog_tool_config],
        ),
    )

    function_call = None

    for candidate in response.candidates or []:

        if not candidate.content:
            continue

        for part in candidate.content.parts or []:

            if part.function_call:

                function_call = part.function_call
                break

        if function_call:
            break

    # =====================================================
    # GEMINI ANSWERED WITHOUT TOOL
    # =====================================================

    if function_call is None:

        return {
            "message": response.text,
            "tool_used": False,
            "policy_checked": False,
            "products": [],
            "policy": None,
        }

    # =====================================================
    # ONLY ACCEPT OUR CATALOG TOOL
    # =====================================================

    if function_call.name != "search_catalog":

        return {
            "message": "I couldn't process that request.",
            "tool_used": False,
            "policy_checked": False,
            "products": [],
            "policy": None,
        }

    # =====================================================
    # EXECUTE REAL DATABASE SEARCH
    # =====================================================

    arguments = dict(
        function_call.args or {}
    )

    products = search_catalog_tool(
        db=db,
        query=arguments.get("query"),
        max_price=arguments.get("max_price"),
        category=arguments.get("category"),
    )

    # =====================================================
    # NO PRODUCTS
    # =====================================================

    if not products:

        return {
            "message": (
                "I couldn't find a suitable product "
                "in the RayBuy catalog."
            ),
            "tool_used": True,
            "policy_checked": False,
            "products": [],
            "policy": None,
        }

    # =====================================================
    # DETERMINE WHETHER USER WANTS TO PURCHASE
    # =====================================================

    purchase_words = [
        "buy",
        "purchase",
        "order",
        "checkout",
        "pay",
        "get it",
        "place an order",
    ]

    wants_to_purchase = any(
        word in user_message.lower()
        for word in purchase_words
    )

    # =====================================================
    # SPENDING POLICY
    #
    # IMPORTANT:
    # This decision is made by Python.
    # Gemini cannot override it.
    # =====================================================

    policy_result = None

    if wants_to_purchase:

        selected_product = products[0]

        policy_result = check_spending_policy(
            db=db,
            user_id=user_id,
            amount=Decimal(
                str(selected_product["price"])
            ),
            category=selected_product["category"],
        )

    # =====================================================
    # BUILD FINAL GEMINI CONTEXT
    # =====================================================

    final_prompt = f"""
User request:
{user_message}

Products returned from the real RayBuy database:

{products}

IMPORTANT PRODUCT DATA RULE:

Only describe attributes that are explicitly present
in the product data above.

Do NOT assume that an ingredient automatically proves
a nutritional attribute.

For example, if the user asks for fiber but the catalog
does not contain fiber information, do not claim a product
is high-fiber. Explain that fiber information is not
available in the current catalog.
"""

    # =====================================================
    # POLICY CONTEXT
    # =====================================================

    if policy_result is not None:

        final_prompt += f"""

Spending policy result from the RayBuy backend:

{policy_result}

IMPORTANT:

The spending policy result is authoritative.

Do not change, reinterpret, or override it.

If "allowed" is false:

- Clearly explain why the purchase cannot proceed.
- Do not suggest bypassing the policy.

If "allowed" is true and "requires_approval" is true:

- Tell the user the purchase is within their policy.
- Clearly ask the user for approval.
- Do not create an order yet.

If "allowed" is true and "requires_approval" is false:

- Tell the user the purchase is permitted.
- Do not claim that an order or payment has happened.
"""

    # =====================================================
    # FINAL INSTRUCTION
    # =====================================================

    final_prompt += """

Provide a concise and helpful response.

Base product recommendations only on the supplied
catalog data.

Do not invent information.

Do not claim that an order was created.

Do not claim that payment was completed.
"""

    # =====================================================
    # SECOND GEMINI TURN
    # =====================================================

    final_response = client.models.generate_content(
        model=MODEL,
        contents=final_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    # =====================================================
    # RETURN API RESPONSE
    # =====================================================

    return {
        "message": final_response.text,
        "tool_used": True,

        # This tells the frontend that real products
        # came from the database.
        "products": products,

        "policy_checked": (
            policy_result is not None
        ),

        "policy": policy_result,
    }