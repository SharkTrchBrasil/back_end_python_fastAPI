# src/api/admin/routes/subscriptions.py
"""
Rotas para gerenciamento de assinaturas
========================================

ENDPOINTS:
- POST   /stores/{id}/subscriptions          → Cria nova assinatura
- POST   /stores/{id}/subscriptions/reactivate → Reativa assinatura cancelada
- GET    /stores/{id}/subscriptions/details   → Detalhes completos
- PATCH  /stores/{id}/subscriptions/card      → Atualiza cartão
- DELETE /stores/{id}/subscriptions           → Cancela assinatura

Autor: Sistema de Billing
Última atualização: 2025-01-21
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.logger import logger

from src.api.admin.services.pagarme_service import pagarme_service, PagarmeError
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.admin.utils.proration import calculate_prorated_charge
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetAuditLoggerDep
from src.core.utils.enums import AuditAction, AuditEntityType
from src.core.utils.validators import (
    validate_cpf,
    validate_cnpj,
    validate_phone,
    validate_cep,
    validate_email
)

router = APIRouter(
    tags=["Subscriptions"]
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PONTO VITAL 1: CRIAR NOVA ASSINATURA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/stores/{store_id}/subscriptions")
async def create_or_reactivate_subscription(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
        subscription_data: CreateStoreSubscription,
):
    """
    ✅ Cria nova assinatura para loja com auditoria completa

    ⚠️ IMPORTANTE: Se a loja já tem assinatura cancelada com dias pagos,
                   use o endpoint /reactivate ao invés deste.
    """

    logger.info(f"✅ Iniciando criação de assinatura para loja {store.id} pelo usuário {user.id}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. VALIDAÇÃO DOS DADOS DA LOJA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    missing_data = []
    invalid_data = []

    # ✅ VALIDAÇÃO DE DOCUMENTO (CPF ou CNPJ)
    document = store.cnpj or user.cpf
    if not document:
        missing_data.append("CPF ou CNPJ")
    else:
        clean_doc = "".join(filter(str.isdigit, document))
        if len(clean_doc) == 11:
            if not validate_cpf(clean_doc):
                invalid_data.append("CPF inválido")
        elif len(clean_doc) == 14:
            if not validate_cnpj(clean_doc):
                invalid_data.append("CNPJ inválido")
        else:
            invalid_data.append("CPF ou CNPJ com tamanho inválido")

    # ✅ VALIDAÇÃO DE EMAIL
    if not user.email:
        missing_data.append("Email")
    elif not validate_email(user.email):
        invalid_data.append("Email inválido")

    # ✅ VALIDAÇÃO DE TELEFONE
    phone = store.phone or user.phone
    if not phone:
        missing_data.append("Telefone")
    else:
        clean_phone = "".join(filter(str.isdigit, phone))
        if not validate_phone(clean_phone):
            invalid_data.append("Telefone inválido (formato: (11) 98765-4321)")

    # ✅ VALIDAÇÃO DE ENDEREÇO COMPLETO
    if not store.street:
        missing_data.append("Rua")
    if not store.number:
        missing_data.append("Número")
    if not store.neighborhood:
        missing_data.append("Bairro")
    if not store.city:
        missing_data.append("Cidade")
    if not store.state:
        missing_data.append("Estado")
    elif len(store.state) != 2:
        invalid_data.append("Estado deve ter 2 letras (ex: SP)")

    # ✅ VALIDAÇÃO DE CEP
    if not store.zip_code:
        missing_data.append("CEP")
    else:
        clean_cep = "".join(filter(str.isdigit, store.zip_code))
        if not validate_cep(clean_cep):
            invalid_data.append("CEP inválido (deve ter 8 dígitos)")

    # ✅ RETORNA ERROS DETALHADOS COM LOG DE AUDITORIA
    if missing_data or invalid_data:
        error_detail = {
            "message": "Complete o cadastro da loja antes de ativar a assinatura"
        }
        if missing_data:
            error_detail["missing_fields"] = missing_data
        if invalid_data:
            error_detail["invalid_fields"] = invalid_data

        audit.log_failed_action(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Validação falhou: {error_detail}"
        )
        db.commit()

        logger.warning(f"Dados inválidos para loja {store.id}: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. VERIFICA SE JÁ TEM ASSINATURA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    existing_subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store.id
    ).order_by(models.StoreSubscription.id.desc()).first()

    # ✅ SE TEM ASSINATURA CANCELADA COM DIAS PAGOS, REDIRECIONA
    if existing_subscription and existing_subscription.status == 'canceled':
        now = datetime.now(timezone.utc)
        end_date = existing_subscription.current_period_end

        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        if end_date and now < end_date:
            days_remaining = (end_date - now).days

            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=f"Tentativa de criar assinatura com {days_remaining} dias restantes"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "subscription_cancelled_with_remaining_days",
                    "message": (
                        f"Você ainda tem {days_remaining} dias pagos até {end_date.strftime('%d/%m/%Y')}. "
                        f"Use o endpoint /reactivate para reativar sem cobrança adicional."
                    ),
                    "days_remaining": days_remaining,
                    "access_until": end_date.isoformat(),
                    "action_required": "POST /stores/{store_id}/subscriptions/reactivate"
                }
            )

    # ✅ SE TEM ASSINATURA ATIVA, RETORNA ERRO
    if existing_subscription and existing_subscription.status in ['active', 'trialing']:
        audit.log_failed_action(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Tentativa de criar assinatura duplicada (status: {existing_subscription.status})"
        )
        db.commit()

        raise HTTPException(
            status_code=400,
            detail={
                "error": "subscription_already_active",
                "message": "Loja já possui assinatura ativa",
                "subscription_id": existing_subscription.id,
                "status": existing_subscription.status
            }
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. BUSCA OU CRIA ASSINATURA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if existing_subscription and existing_subscription.status == 'expired':
        subscription = existing_subscription
        logger.info(f"Reutilizando assinatura expirada: ID {subscription.id}")
    else:
        main_plan = db.query(models.Plans).filter_by(
            plan_name='Plano Parceiro'
        ).first()

        if not main_plan:
            logger.error("Plano 'Plano Parceiro' não encontrado no banco")

            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error="Plano 'Plano Parceiro' não encontrado no sistema"
            )
            db.commit()

            raise HTTPException(
                status_code=500,
                detail="Erro de configuração: Plano não encontrado"
            )

        subscription = models.StoreSubscription(
            store=store,
            plan=main_plan,
            status="expired",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=30),
            current_period_end=datetime.now(timezone.utc),
        )
        db.add(subscription)
        db.flush()

        logger.info(f"Nova assinatura criada: ID {subscription.id}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. VALIDAÇÃO DO TOKEN DO CARTÃO
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if not subscription_data.card or not subscription_data.card.payment_token:
        audit.log_failed_action(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error="Token do cartão não fornecido"
        )
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="Token do cartão é obrigatório"
        )

    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5. INTEGRAÇÃO COM PAGAR.ME
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        if not store.pagarme_customer_id:
            logger.info(f"Criando customer no Pagar.me para loja {store.id}")

            customer_response = pagarme_service.create_customer(
                email=user.email,
                name=user.name or store.name,
                document=store.cnpj or user.cpf,
                phone=store.phone or user.phone,
                store_id=store.id
            )
            store.pagarme_customer_id = customer_response["id"]

            logger.info(f"Customer criado: {store.pagarme_customer_id}")

        logger.info(f"Adicionando cartão para customer {store.pagarme_customer_id}")

        billing_address = {
            "line_1": f"{store.street}, {store.number}",
            "line_2": store.complement if store.complement else None,
            "zip_code": "".join(filter(str.isdigit, store.zip_code)),
            "city": store.city,
            "state": store.state[:2].upper(),
            "country": "BR"
        }

        billing_address = {k: v for k, v in billing_address.items() if v is not None}

        try:
            card_response = pagarme_service.create_card(
                customer_id=store.pagarme_customer_id,
                card_token=subscription_data.card.payment_token,
                billing_address=billing_address
            )

            card_id = card_response.get("id")

            if not card_id:
                logger.error("❌ Resposta do Pagar.me NÃO contém 'id' do cartão!")

                audit.log_failed_action(
                    action=AuditAction.CREATE_SUBSCRIPTION,
                    entity_type=AuditEntityType.SUBSCRIPTION,
                    error="Gateway não retornou ID do cartão"
                )
                db.commit()

                raise HTTPException(
                    status_code=500,
                    detail="Erro ao processar cartão: ID não retornado pelo Pagar.me"
                )

            store.pagarme_card_id = card_id
            logger.info(f"✅ Card ID salvo: {card_id}")

        except PagarmeError as card_error:
            logger.error(f"❌ Falha ao adicionar cartão: {card_error}")

            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=f"Cartão recusado: {str(card_error)}"
            )
            db.commit()

            if "verification failed" in str(card_error).lower():
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Cartão recusado",
                        "details": [
                            "Verifique se o cartão está ativo",
                            "Confirme os dados do cartão",
                            "Tente com outro cartão",
                            "Em ambiente de teste, use: 5555 5555 5555 4444"
                        ]
                    }
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Erro ao processar cartão: {str(card_error)}"
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6. COBRANÇA PROPORCIONAL
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        proration_details = calculate_prorated_charge(subscription.plan)
        prorated_amount_cents = proration_details["amount_in_cents"]

        logger.info("━" * 60)
        logger.info("💰 [Subscription] Processando cobrança inicial")
        logger.info(
            f"   Período: {proration_details['period_start'].date()} → {proration_details['period_end'].date()}")
        logger.info(f"   Valor: R$ {prorated_amount_cents / 100:.2f}")
        logger.info("━" * 60)

        monthly_charge = None
        charge_id = None

        if prorated_amount_cents > 0:
            logger.info(f"Criando cobrança de R$ {prorated_amount_cents / 100:.2f}")

            charge_response = pagarme_service.create_charge(
                customer_id=store.pagarme_customer_id,
                card_id=store.pagarme_card_id,
                amount_in_cents=prorated_amount_cents,
                description=proration_details["description"],
                store_id=store.id,
                metadata={"type": "prorated_charge"}
            )

            charge_id = charge_response['id']
            logger.info(f"Cobrança criada: {charge_id}")

            monthly_charge = models.MonthlyCharge(
                store_id=store.id,
                subscription_id=subscription.id,
                charge_date=datetime.now(timezone.utc).date(),
                billing_period_start=proration_details["period_start"].date(),
                billing_period_end=proration_details["period_end"].date(),
                total_revenue=Decimal("0"),
                calculated_fee=Decimal(str(prorated_amount_cents / 100)),
                status="pending",
                gateway_transaction_id=charge_id,
                charge_metadata={
                    "type": "prorated_charge",
                    "description": proration_details["description"]
                }
            )
            db.add(monthly_charge)
        else:
            logger.info("🎉 1º mês GRÁTIS - Nenhuma cobrança criada")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7. ATIVA ASSINATURA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc)
        subscription.current_period_end = proration_details["new_period_end_date"]
        subscription.canceled_at = None

        logger.info("━" * 60)
        logger.info("✅ [Subscription] Assinatura ativada!")
        logger.info(f"   Status: active")
        logger.info(
            f"   Período: {subscription.current_period_start.date()} → {subscription.current_period_end.date()}")
        logger.info(f"   Próxima cobrança: {subscription.current_period_end.date() + timedelta(days=1)}")
        logger.info("━" * 60)

        # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
        plan_name = subscription.plan.plan_name if subscription.plan else "N/A"
        plan_price = float(subscription.plan.minimum_fee) / 100 if subscription.plan else 0
        period_start = subscription.current_period_start.isoformat() if subscription.current_period_start else None
        period_end = subscription.current_period_end.isoformat() if subscription.current_period_end else None

        audit.log(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            changes={
                "store_name": store.name,
                "plan_name": plan_name,
                "plan_price": plan_price,
                "customer_id": store.pagarme_customer_id,
                "card_id": store.pagarme_card_id,
                "charge_id": charge_id,
                "charged_amount": prorated_amount_cents / 100 if monthly_charge else 0,
                "period_start": period_start,
                "period_end": period_end,
                "is_free_trial": prorated_amount_cents == 0
            },
            description=(
                f"Assinatura criada para loja '{store.name}' - "
                f"Plano: {plan_name} - "
                f"Valor: R$ {prorated_amount_cents / 100:.2f}"
            )
        )

        db.commit()

        logger.info(f"✅ Assinatura {subscription.id} ativada com sucesso!")

        await admin_emit_store_updated(db, store.id)

        return {
            "status": "success",
            "message": "Assinatura ativada com sucesso!",
            "subscription": {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start.isoformat(),
                "current_period_end": subscription.current_period_end.isoformat(),
                "charge_id": monthly_charge.id if monthly_charge else None,
                "charged_amount": prorated_amount_cents / 100 if monthly_charge else 0
            }
        }

    except PagarmeError as e:
        db.rollback()

        audit.log_failed_action(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro Pagar.me: {str(e)}"
        )
        db.commit()

        logger.error(f"Erro Pagar.me: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao processar pagamento: {str(e)}"
        )

    except Exception as e:
        db.rollback()

        audit.log_failed_action(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro inesperado: {str(e)}"
        )
        db.commit()

        logger.error(f"Erro inesperado: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Erro ao processar assinatura. Tente novamente."
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PONTO VITAL 2: REATIVAR ASSINATURA CANCELADA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/stores/{store_id}/subscriptions/reactivate")
async def reactivate_subscription(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
        card_data: Optional[CreateStoreSubscription] = None
):
    """
    ✅ REATIVA assinatura cancelada de forma inteligente com auditoria

    CENÁRIOS:
    1. Cancelada + Ainda tem dias pagos → Reativa SEM cobrar
    2. Cancelada + Expirada → Exige novo cartão e cobra proporcional
    """

    logger.info(f"🔄 Tentativa de reativação para loja {store.id}")

    subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store.id
    ).order_by(models.StoreSubscription.id.desc()).first()

    if not subscription:
        audit.log_failed_action(
            action=AuditAction.REACTIVATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error="Nenhuma assinatura encontrada"
        )
        db.commit()

        raise HTTPException(404, "Nenhuma assinatura encontrada")

    now = datetime.now(timezone.utc)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CENÁRIO 2: EXPIRADA OU NUNCA TEVE → EXIGE NOVO CARTÃO
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if subscription.status in ['canceled', 'expired']:
        logger.info(f"Reativação de assinatura expirada (precisa de cartão)")

        if not card_data or not card_data.card or not card_data.card.payment_token:
            audit.log_failed_action(
                action=AuditAction.REACTIVATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error="Token do cartão não fornecido para assinatura expirada"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "card_required",
                    "message": "Token do cartão é obrigatório para reativar assinatura expirada",
                    "hint": "Use o mesmo fluxo de criação de assinatura"
                }
            )

        return await create_or_reactivate_subscription(request, db, store, user, audit, card_data)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ASSINATURA JÁ ESTÁ ATIVA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    audit.log_failed_action(
        action=AuditAction.REACTIVATE_SUBSCRIPTION,
        entity_type=AuditEntityType.SUBSCRIPTION,
        error=f"Tentativa de reativar assinatura já ativa (status: {subscription.status})"
    )
    db.commit()

    raise HTTPException(
        status_code=400,
        detail={
            "error": "subscription_already_active",
            "message": "Assinatura já está ativa",
            "status": subscription.status
        }
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. DETALHES DA ASSINATURA (SEM AUDITORIA - APENAS LEITURA)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/stores/{store_id}/subscriptions/details")
async def get_subscription_details(
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
):
    """
    Retorna detalhes completos da assinatura (Versão Refatorada)
    """
    subscription_details = SubscriptionService.get_subscription_details(store=store, db=db)

    if not subscription_details:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma assinatura encontrada"
        )

    return subscription_details


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PONTO VITAL 3: ATUALIZAR CARTÃO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.patch("/stores/{store_id}/subscriptions/card")
async def update_subscription_card(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
        card_data: CreateStoreSubscription,
):
    """
    Atualiza o cartão de crédito da assinatura com auditoria

    - Substitui o cartão antigo
    - Mantém a assinatura ativa
    - Não cria cobrança (só atualiza o meio de pagamento)
    """

    logger.info(f"Atualizando cartão para loja {store.id}...")

    subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store.id,
        models.StoreSubscription.status.in_(['active', 'trialing'])
    ).first()

    if not subscription:
        audit.log_failed_action(
            action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error="Nenhuma assinatura ativa encontrada"
        )
        db.commit()

        raise HTTPException(
            status_code=404,
            detail="Nenhuma assinatura ativa encontrada"
        )

    try:
        if not card_data.card or not card_data.card.payment_token:
            audit.log_failed_action(
                action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
                entity_type=AuditEntityType.SUBSCRIPTION,
                entity_id=subscription.id,
                error="Token do cartão não fornecido"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail="Token do cartão é obrigatório"
            )

        billing_address = {
            "line_1": f"{store.street}, {store.number}",
            "zip_code": "".join(filter(str.isdigit, store.zip_code)),
            "city": store.city,
            "state": store.state[:2].upper(),
            "country": "BR"
        }

        card_response = pagarme_service.create_card(
            customer_id=store.pagarme_customer_id,
            card_token=card_data.card.payment_token,
            billing_address=billing_address
        )

        logger.info(f"Novo cartão criado: {card_response['id']}")

        old_card_id = store.pagarme_card_id
        store.pagarme_card_id = card_response["id"]

        audit.log(
            action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            changes={
                "store_name": store.name,
                "old_card_id": old_card_id,
                "new_card_id": card_response["id"],
                "card_last_four": card_response.get("last_four_digits"),
                "card_brand": card_response.get("brand")
            },
            description=f"Cartão atualizado - Final: {card_response.get('last_four_digits')} - Bandeira: {card_response.get('brand')}"
        )

        db.commit()

        logger.info(f"Cartão atualizado: {old_card_id} → {card_response['id']}")

        await admin_emit_store_updated(db, store.id)
        await emit_store_updated(db, store.id)

        return {
            "status": "success",
            "message": "Cartão atualizado com sucesso!",
            "card": {
                "id": card_response["id"],
                "last_four_digits": card_response.get("last_four_digits"),
                "brand": card_response.get("brand")
            }
        }

    except PagarmeError as e:
        db.rollback()

        audit.log_failed_action(
            action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            error=f"Erro Pagar.me: {str(e)}"
        )
        db.commit()

        logger.error(f"Erro Pagar.me: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        db.rollback()

        audit.log_failed_action(
            action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            error=f"Erro inesperado: {str(e)}"
        )
        db.commit()

        logger.error(f"Erro inesperado: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar cartão. Tente novamente."
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PONTO VITAL 4: CANCELAR ASSINATURA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.delete("/stores/{store_id}/subscriptions")
async def cancel_subscription(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
):
    """
    Cancela a assinatura com auditoria completa

    VERSÃO FINAL BLINDADA:
    - Trata canceled_at NULL
    - Trata datas sem timezone
    - Valida todos os status possíveis
    - Logs detalhados
    - Mensagens amigáveis

    COMPORTAMENTO:
    - NÃO desconecta chatbot imediatamente
    - NÃO fecha loja imediatamente
    - Mantém tudo funcionando até o fim do período pago
    - Job automático fecha tudo no último dia (00:05 UTC)
    """

    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. BUSCA ASSINATURA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        subscription = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store.id
        ).order_by(models.StoreSubscription.id.desc()).first()

        if not subscription:
            logger.error(f"Loja {store.id} não possui nenhuma assinatura")

            audit.log_failed_action(
                action=AuditAction.CANCEL_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error="Nenhuma assinatura encontrada"
            )
            db.commit()

            raise HTTPException(
                status_code=404,
                detail="Nenhuma assinatura encontrada para esta loja"
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. NORMALIZA DADOS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        now = datetime.now(timezone.utc)
        end_date = subscription.current_period_end

        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        has_access = end_date and now < end_date
        days_remaining = (end_date - now).days if has_access else 0

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. SE JÁ ESTÁ CANCELADA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        if subscription.status == "canceled":
            logger.info(f"Assinatura {subscription.id} já estava cancelada")

            if subscription.canceled_at:
                try:
                    if subscription.canceled_at.tzinfo is None:
                        canceled_at_aware = subscription.canceled_at.replace(tzinfo=timezone.utc)
                    else:
                        canceled_at_aware = subscription.canceled_at
                    canceled_at_str = canceled_at_aware.strftime('%d/%m/%Y %H:%M')
                    canceled_at_iso = canceled_at_aware.isoformat()
                except Exception as e:
                    logger.warning(f"Erro ao formatar canceled_at: {e}")
                    canceled_at_str = "uma data anterior"
                    canceled_at_iso = None
            else:
                canceled_at_str = "uma data anterior"
                canceled_at_iso = None

            audit.log_failed_action(
                action=AuditAction.CANCEL_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                entity_id=subscription.id,
                error=f"Tentativa de cancelar assinatura já cancelada em {canceled_at_str}"
            )
            db.commit()

            return {
                "status": "already_canceled",
                "message": (
                    f"Esta assinatura já foi cancelada em {canceled_at_str}. "
                    f"{'Você ainda tem acesso até ' + end_date.strftime('%d/%m/%Y') + f' ({days_remaining} dias restantes).' if has_access else 'O acesso já expirou.'}"
                ),
                "canceled_at": canceled_at_iso,
                "access_until": end_date.isoformat() if end_date else None,
                "has_access": has_access,
                "days_remaining": days_remaining
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. VALIDA SE PODE CANCELAR
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        if subscription.status not in ['active', 'trialing']:
            logger.error(f"Tentativa de cancelar assinatura com status '{subscription.status}'")

            audit.log_failed_action(
                action=AuditAction.CANCEL_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                entity_id=subscription.id,
                error=f"Tentativa de cancelar assinatura com status inválido: {subscription.status}"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail=f"Não é possível cancelar assinatura com status '{subscription.status}'."
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5. PROCESSA CANCELAMENTO
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        old_status = subscription.status
        subscription.status = "canceled"
        subscription.canceled_at = datetime.now(timezone.utc)

        logger.info(f"Cancelando assinatura {subscription.id}: {old_status} → canceled")
        logger.info(f"   Cancelada em: {subscription.canceled_at.isoformat()}")
        logger.info(f"   Acesso até: {end_date.isoformat() if end_date else 'N/A'}")
        logger.info(f"   Dias restantes: {days_remaining}")

        audit.log(
            action=AuditAction.CANCEL_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            changes={
                "store_name": store.name,
                "old_status": old_status,
                "new_status": "canceled",
                "canceled_at": subscription.canceled_at.isoformat(),
                "access_until": end_date.isoformat() if end_date else None,
                "days_remaining": days_remaining
            },
            description=f"Assinatura cancelada - {days_remaining} dias restantes até {end_date.strftime('%d/%m/%Y') if end_date else 'N/A'}"
        )

        db.commit()

        logger.info(f"Assinatura {subscription.id} cancelada com sucesso!")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6. EMITE EVENTOS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        try:
            await admin_emit_store_updated(db, store.id)
        except Exception as e:
            logger.error(f"Erro ao emitir evento admin: {e}", exc_info=True)

        try:
            await emit_store_updated(db, store.id)
        except Exception as e:
            logger.error(f"Erro ao emitir evento app: {e}", exc_info=True)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7. RETORNA RESPOSTA DETALHADA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        end_date_str = end_date.strftime('%d/%m/%Y') if end_date else "desconhecida"

        return {
            "status": "success",
            "message": (
                f"Assinatura cancelada com sucesso!\n\n"
                f"Você manterá acesso COMPLETO até {end_date_str} ({days_remaining} dias restantes).\n\n"
                f"Isso inclui:\n"
                f"• Chatbot ativo e recebendo pedidos\n"
                f"• Loja aberta para clientes\n"
                f"• Acesso total ao painel admin\n\n"
                f"No dia {end_date_str} às 00:05 UTC, o sistema irá automaticamente:\n"
                f"• Desconectar o chatbot\n"
                f"• Fechar a loja\n"
                f"• Bloquear o acesso ao painel\n\n"
                f"Você pode reativar a qualquer momento antes dessa data."
            ),
            "canceled_at": subscription.canceled_at.isoformat(),
            "access_until": end_date.isoformat() if end_date else None,
            "days_remaining": days_remaining,
            "chatbot_active_until": end_date.isoformat() if end_date else None,
            "store_open_until": end_date.isoformat() if end_date else None,
            "actions_taken": [
                "Assinatura marcada como cancelada",
                f"Chatbot permanecerá ativo até {end_date_str}",
                f"Loja permanecerá aberta até {end_date_str}",
                "Sistema fechará automaticamente no último dia"
            ]
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Erro crítico ao cancelar assinatura: {e}", exc_info=True)
        db.rollback()

        audit.log_failed_action(
            action=AuditAction.CANCEL_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro crítico: {str(e)}"
        )
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar cancelamento. Tente novamente ou contate o suporte."
        )

        #1: CANCELADA MAS AINDA TEM DIAS PAGOS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if subscription.status == 'canceled':
        end_date = subscription.current_period_end

        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        if end_date and now < end_date:
            days_remaining = (end_date - now).days

            logger.info(f"🔄 Reativando assinatura {subscription.id} com {days_remaining} dias já pagos")

            subscription.status = 'active'
            subscription.canceled_at = None

            operation_config = db.query(models.StoreOperationConfig).filter_by(
                store_id=store.id
            ).first()

            if operation_config:
                operation_config.is_store_open = True
                logger.info(f"  🔓 Loja reaberta")

            chatbot_config = db.query(models.StoreChatbotConfig).filter_by(
                store_id=store.id
            ).first()

            if chatbot_config:
                chatbot_config.is_active = True
                logger.info(f"  🤖 Chatbot marcado como ativo (precisa reconectar)")

            audit.log(
                action=AuditAction.REACTIVATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                entity_id=subscription.id,
                changes={
                    "store_name": store.name,
                    "days_remaining": days_remaining,
                    "access_until": end_date.isoformat(),
                    "charged": False,
                    "charge_amount": 0
                },
                description=f"Assinatura reativada sem cobrança - {days_remaining} dias restantes"
            )

            db.commit()

            await admin_emit_store_updated(db, store.id)
            await emit_store_updated(db, store.id)

            return {
                "status": "reactivated",
                "message": (
                    f"✅ Assinatura reativada com sucesso! "
                    f"Você ainda tinha {days_remaining} dias pagos. "
                    f"Não foi feita nenhuma nova cobrança. "
                    f"Seu acesso vai até {end_date.strftime('%d/%m/%Y')}. "
                    f"\n\n⚠️ ATENÇÃO: Reconecte o chatbot no painel para voltar a receber pedidos."
                ),
                "subscription_id": subscription.id,
                "access_until": end_date.isoformat(),
                "days_remaining": days_remaining,
                "charged": False,
                "charge_amount": 0,
                "actions_required": [
                    "Reconectar chatbot (QR Code)"
                ]
            }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CENÁRIO