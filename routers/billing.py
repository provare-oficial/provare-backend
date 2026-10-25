"""
Router de cobrança via Stripe
"""
import logging
import stripe
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional

from database import get_database
from auth_utils import get_current_user, get_current_company
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["cobrança"])

stripe.api_key = settings.stripe_secret_key

PLANS = {
    "starter": {
        "name": "Starter",
        "price_brl": 197,
        "price_id": settings.stripe_price_starter,
        "description": "Até 10 projetos ativos",
        "features": ["10 projetos ativos", "Provare Book ilimitado", "Upload de fotos e vídeos", "QR de autenticidade"],
    },
    "pro": {
        "name": "Pro",
        "price_brl": 397,
        "price_id": settings.stripe_price_pro,
        "description": "Projetos ilimitados + IA",
        "features": ["Projetos ilimitados", "Mensagens WhatsApp com IA", "Provare Book white-label", "Suporte prioritário"],
        "recommended": True,
    },
    "studio": {
        "name": "Studio",
        "price_brl": 797,
        "price_id": settings.stripe_price_studio,
        "description": "Multi-usuário + domínio próprio",
        "features": ["Tudo do Pro", "Até 10 usuários", "Domínio personalizado", "Onboarding dedicado"],
    },
}


@router.get("/plans")
async def get_plans():
    """Retorna os planos disponíveis (sem price_id — dado interno)."""
    return [
        {k: v for k, v in plan.items() if k != "price_id"}
        for plan in PLANS.values()
    ]


@router.post("/create-checkout")
async def create_checkout(
    plan: str,
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """Cria uma sessão de checkout no Stripe para assinar um plano."""
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    plan_data = PLANS[plan]
    if not plan_data["price_id"]:
        raise HTTPException(status_code=503, detail="Plano não configurado ainda")

    try:
        # Cria ou recupera o customer no Stripe
        stripe_customer_id = company.get("stripe_customer_id")
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=company["email"],
                name=company["name"],
                metadata={"company_id": company["company_id"]},
            )
            stripe_customer_id = customer.id
            db = get_database()
            await db.companies.update_one(
                {"company_id": company["company_id"]},
                {"$set": {"stripe_customer_id": stripe_customer_id}},
            )

        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": plan_data["price_id"], "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.app_url}/configuracoes?checkout=success",
            cancel_url=f"{settings.app_url}/configuracoes?checkout=canceled",
            metadata={"company_id": company["company_id"], "plan": plan},
        )
        return {"checkout_url": session.url}

    except stripe.error.StripeError as e:
        logger.error(f"Erro no Stripe: {e}")
        raise HTTPException(status_code=502, detail="Erro ao criar sessão de pagamento")


@router.get("/portal")
async def billing_portal(
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """Redireciona para o portal do cliente no Stripe (gerenciar assinatura)."""
    if not company.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="Empresa sem assinatura ativa")

    try:
        session = stripe.billing_portal.Session.create(
            customer=company["stripe_customer_id"],
            return_url=f"{settings.app_url}/configuracoes",
        )
        return {"portal_url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=502, detail="Erro ao acessar portal de pagamento")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Webhook do Stripe — atualiza status do plano automaticamente.
    Configurar no painel Stripe: endpoint /billing/webhook
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura inválida")

    db = get_database()
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        company_id = data.get("metadata", {}).get("company_id")
        plan = data.get("metadata", {}).get("plan", "pro")
        if company_id:
            await db.companies.update_one(
                {"company_id": company_id},
                {"$set": {
                    "plan": plan,
                    "plan_status": "active",
                    "stripe_subscription_id": data.get("subscription"),
                }},
            )

    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        customer_id = data.get("customer")
        if customer_id:
            await db.companies.update_one(
                {"stripe_customer_id": customer_id},
                {"$set": {"plan_status": "canceled"}},
            )

    elif event_type == "customer.subscription.updated":
        customer_id = data.get("customer")
        status = data.get("status")
        if customer_id and status:
            plan_status = "active" if status == "active" else "canceled"
            await db.companies.update_one(
                {"stripe_customer_id": customer_id},
                {"$set": {"plan_status": plan_status}},
            )

    return {"received": True}
