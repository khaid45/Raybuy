# RayBuy 🚀

### AI-Powered Agentic Commerce for Food Ordering

RayBuy is an AI-powered food commerce platform that lets users discover products, receive AI recommendations, apply spending policies, and complete purchases through Razorpay Test Mode.

Built for the **Razorpay AI Buildathon — Track 01: AI Growth & Agentic Commerce**.

---

## 🎯 What RayBuy Does

RayBuy combines conversational AI with a real payment flow to create a bounded and explainable agentic shopping experience.

A user can:

- 🔎 Search the real product catalog
- 🤖 Ask RayBuy AI for product recommendations
- 💰 Set a spending limit/policy
- 🛒 Select a product and initiate a purchase
- 🔐 Approve an AI-recommended purchase
- 💳 Complete payment using Razorpay Checkout
- ✅ Verify the payment securely on the backend
- 🧾 Record the transaction in an audit trail
- ⚠️ Handle failed payments gracefully

---

## 🤖 Agentic Commerce Flow

```text
User
  │
  ▼
RayBuy Web App
  │
  ├── Catalog Search
  │
  └── RayBuy AI
        │
        ▼
   Product Recommendation
        │
        ▼
   Spending Policy Check
        │
        ▼
   Purchase Approval
        │
        ▼
   Create Razorpay Order
        │
        ▼
   Razorpay Checkout
        │
        ├── Success ──► Server-side Verification
        │                    │
        │                    ▼
        │               Paid Order
        │                    │
        │                    ▼
        │                Audit Log
        │
        └── Failure ──► Order remains pending
