"""
Rotas para gerenciamento de assinaturas
========================================
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from fastapi.logger import logger

from src.api.admin.services.billing_preview_service import BillingPreviewService
from src.api.admin.services.billing_report_service import BillingReportService
from src.api.admin.services.pagarme_service import pagarme_service, PagarmeError
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.admin.utils.proration import calculate_prorated_charge
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep
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


@router.post("/stores/{store_id}/subscriptions")
async def create_or_reactivate_subscription(
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    subscription_data: CreateStoreSubscription,
):
    """
    ✅ Cria ou reativa uma assinatura de loja.

    O GetStoreDep já valida:
    - Se a loja existe
    - Se o usuário tem acesso à loja
    - Se o usuário tem permissão adequada

    Args:
        db: Sessão do banco de dados
        store: Loja (já validada pelo GetStoreDep)
        user: Usuário autenticado
        subscription_data: Dados do cartão tokenizado

    Returns:
        Dados da assinatura ativada

    Raises:
        400: Dados inválidos ou incompletos
        500: Erro no processamento
    """

    logger.info(f"✅ Iniciando criação de assinatura para loja {store.id} pelo usuário {user.id}")

    # ═══════════════════════════════════════════════════════════
    # 1. VALIDAÇÃO DOS DADOS DA LOJA
    # ═══════════════════════════════════════════════════════════

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

    # ✅ RETORNA ERROS DETALHADOS
    if missing_data or invalid_data:
        error_detail = {
            "message": "Complete o cadastro da loja antes de ativar a assinatura"
        }
        if missing_data:
            error_detail["missing_fields"] = missing_data
        if invalid_data:
            error_detail["invalid_fields"] = invalid_data

        logger.warning(f"Dados inválidos para loja {store.id}: {error_detail}")

        raise HTTPException(status_code=400, detail=error_detail)

    # ═══════════════════════════════════════════════════════════
    # 2. BUSCA OU CRIA ASSINATURA
    # ═══════════════════════════════════════════════════════════

    subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store.id
    ).first()

    if not subscription:
        main_plan = db.query(models.Plans).filter_by(
            plan_name='Plano Parceiro'
        ).first()

        if not main_plan:
            logger.error("Plano 'Plano Parceiro' não encontrado no banco")
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

    # ═══════════════════════════════════════════════════════════
    # 3. VALIDAÇÃO DO TOKEN DO CARTÃO
    # ═══════════════════════════════════════════════════════════

    if not subscription_data.card or not subscription_data.card.payment_token:
        raise HTTPException(
            status_code=400,
            detail="Token do cartão é obrigatório"
        )

    try:
        # ═══════════════════════════════════════════════════════
        # 4. INTEGRAÇÃO COM PAGAR.ME
        # ═══════════════════════════════════════════════════════

        # ✅ Cria customer se não existir
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

        # ✅ Adiciona cartão
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
                # verify_card é automático: False em test, True em production
            )
            store.pagarme_card_id = card_response["id"]
            logger.info(f"✅ Cartão adicionado: {store.pagarme_card_id}")

        except PagarmeError as card_error:
            logger.error(f"❌ Falha ao adicionar cartão: {card_error}")

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

        # ═══════════════════════════════════════════════════════
        # 5. COBRANÇA PROPORCIONAL
        # ═══════════════════════════════════════════════════════

        proration_details = calculate_prorated_charge(subscription.plan)
        prorated_amount_cents = proration_details["amount_in_cents"]

        monthly_charge = None

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

            logger.info(f"Cobrança criada: {charge_response['id']}")

            monthly_charge = models.MonthlyCharge(
                store_id=store.id,
                subscription_id=subscription.id,
                charge_date=datetime.now(timezone.utc).date(),
                billing_period_start=proration_details.get("period_start", datetime.now(timezone.utc)).date(),
                billing_period_end=proration_details.get("period_end", subscription.current_period_end).date(),
                total_revenue=Decimal("0"),
                calculated_fee=Decimal(str(prorated_amount_cents / 100)),
                status="pending",
                gateway_transaction_id=charge_response["id"],
                charge_metadata={
                    "type": "prorated_charge",
                    "description": proration_details["description"]
                }
            )
            db.add(monthly_charge)

            logger.info(f"MonthlyCharge registrado: {charge_response['id']}")

        # ═══════════════════════════════════════════════════════
        # 6. ATIVA ASSINATURA
        # ═══════════════════════════════════════════════════════

        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc)
        subscription.current_period_end = proration_details["new_period_end_date"]

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
                "charge_id": monthly_charge.id if monthly_charge else None
            }
        }

    except PagarmeError as e:
        db.rollback()
        logger.error(f"Erro Pagar.me: {e}")

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao processar pagamento: {str(e)}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erro inesperado: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Erro ao processar assinatura. Tente novamente."
        )


@router.get("/stores/{store_id}/subscriptions/details")
async def get_subscription_details(
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
):
    """
    🎯 Retorna detalhes completos da assinatura ativa.

    Inclui:
    - Dados da assinatura atual
    - Preview de faturamento
    - Histórico de cobranças
    - Informações do cartão (mascarado)
    """

    subscription = store.active_subscription

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma assinatura ativa encontrada"
        )

    # ✅ Preview de faturamento
    billing_preview = BillingPreviewService.get_billing_preview(db, store)

    # ✅ Histórico de cobranças (últimos 6 meses)
    billing_history = BillingReportService.get_store_history(db, store.id, months=6)

    # ✅ Buscar dados REAIS do cartão no Pagar.me
    card_info = None
    if store.pagarme_card_id and store.pagarme_customer_id:
        try:
            logger.info(f"Buscando informações do cartão {store.pagarme_card_id}")

            card_response = pagarme_service.get_card(
                customer_id=store.pagarme_customer_id,
                card_id=store.pagarme_card_id
            )

            # Monta resposta com dados reais mascarados
            card_info = {
                "masked_number": f"************{card_response.get('last_four_digits', '****')}",
                "brand": card_response.get('brand', 'Desconhecida'),
                "status": card_response.get('status', 'active'),
                "holder_name": card_response.get('holder_name'),
                "exp_month": card_response.get('exp_month'),
                "exp_year": card_response.get('exp_year'),
            }

            logger.info(f"✅ Cartão encontrado: {card_info['brand']} {card_info['masked_number']}")

        except PagarmeError as e:
            logger.warning(f"⚠️ Erro ao buscar cartão do Pagar.me: {e}")
            # Fallback: retornar dados genéricos
            card_info = {
                "masked_number": "************",
                "brand": "Cartão Cadastrado",
                "status": "active"
            }

        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar cartão: {e}")
            card_info = {
                "masked_number": "************",
                "brand": "Erro ao buscar",
                "status": "unknown"
            }

    return {
        "subscription": {
            "id": subscription.id,
            "status": subscription.status,
            "is_blocked": subscription.is_blocked,
            "warning_message": subscription.warning_message,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": subscription.current_period_end.isoformat(),
            "plan": {
                "id": subscription.plan.id,
                "name": subscription.plan.plan_name,
                "minimum_fee": subscription.plan.minimum_fee,
                "revenue_percentage": float(subscription.plan.revenue_percentage),
                "revenue_cap_fee": subscription.plan.revenue_cap_fee,
            } if subscription.plan else None,
        },
        "billing_preview": billing_preview,
        "billing_history": billing_history,
        "card_info": card_info,
        "can_cancel": subscription.status in ["active", "trialing"],
    }


@router.delete("/stores/{store_id}/subscriptions")
async def cancel_subscription(
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
):
    """
    ⚠️ Cancela a assinatura da loja.

    - Muda status para "canceled"
    - Mantém acesso até o fim do período pago
    - Bloqueia renovação automática
    """

    subscription = store.active_subscription

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma assinatura ativa encontrada"
        )

    # Não pode cancelar se já está cancelada
    if subscription.status == "canceled":
        raise HTTPException(
            status_code=400,
            detail="Esta assinatura já foi cancelada"
        )

    # ✅ Cancela no Pagar.me (se houver ID de assinatura recorrente)
    if subscription.gateway_subscription_id:
        try:
            logger.info(f"Cancelando assinatura {subscription.gateway_subscription_id} no Pagar.me")
            # pagarme_service.cancel_subscription(subscription.gateway_subscription_id)
            # TODO: Implementar quando houver assinaturas recorrentes
            pass
        except Exception as e:
            logger.error(f"Erro ao cancelar no Pagar.me: {e}")
            # Não bloqueia o cancelamento local

    # ✅ Atualiza status no banco
    subscription.status = "canceled"
    subscription.canceled_at = datetime.now(timezone.utc)

    db.commit()

    logger.info(f"✅ Assinatura {subscription.id} cancelada pelo usuário {user.id}")

    await admin_emit_store_updated(db, store.id)

    return {
        "status": "success",
        "message": "Assinatura cancelada com sucesso",
        "access_until": subscription.current_period_end.isoformat()
    }