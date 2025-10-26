# src/api/admin/routes/subscriptions_v2.py
"""
✅ VERSÃO 2 - ENDPOINTS DE ASSINATURA (Robusta e Profissional)

Estados únicos na DB:
- status: 'trial' | 'active' | 'canceled'
- canceled_at: datetime | null

Estados derivados (calculados em tempo real):
- 'active' → 'warning' → 'past_due' → 'expired'
- 'canceled' + dias → OK | sem dias → EXPIRED
"""

from datetime import datetime, timezone, timedelta

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.logger import logger

from src.api.admin.services.pagarme_service import pagarme_service, PagarmeError
from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_service import StoreService
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetAuditLoggerDep, GetStoreForSubscriptionDep
from src.core.utils.enums import AuditAction, AuditEntityType
from src.socketio_instance import sio

router = APIRouter(tags=["Subscriptions"])


def _normalize_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """Normaliza datetime para UTC"""
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _has_days_remaining(period_end: Optional[datetime]) -> bool:
    """Verifica se ainda tem dias restantes"""
    if not period_end:
        return False
    normalized = _normalize_datetime(period_end)
    now = datetime.now(timezone.utc)
    return now < normalized


def _get_days_remaining(period_end: Optional[datetime]) -> int:
    """Calcula dias restantes"""
    if not period_end:
        return 0
    normalized = _normalize_datetime(period_end)
    now = datetime.now(timezone.utc)
    if now < normalized:
        return (normalized - now).days
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 ENDPOINT 1: CRIAR NOVA ASSINATURA (TRIAL/EXPIRED → ACTIVE)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/stores/{store_id}/subscriptions")
async def create_subscription(
        request: Request,
        db: GetDBDep,
        store: GetStoreForSubscriptionDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
        subscription_data: CreateStoreSubscription,
):
    """
    ✅ Cria nova assinatura ATIVA (paga)

    Validações:
    - Dados da loja completos
    - Cartão válido
    - Sem assinatura ativa ou TRIAL com dias

    Transições:
    - TRIAL expirado → ACTIVE
    - SEM assinatura → ACTIVE
    - Assinatura CANCELED + expirada → ACTIVE
    """

    logger.info(f"📝 Criando assinatura para loja {store.id}...")

    try:
        # ─────────────────────────────────────────────────────────────────
        # 1. VALIDAÇÃO DE DADOS DA LOJA
        # ─────────────────────────────────────────────────────────────────

        missing_data = []

        if not (store.cnpj or user.cpf):
            missing_data.append("CPF ou CNPJ")

        if not user.email:
            missing_data.append("Email")

        if not (store.phone or user.phone):
            missing_data.append("Telefone")

        if not store.street or not store.number:
            missing_data.append("Endereço")

        if not store.neighborhood or not store.city or not store.state:
            missing_data.append("Localidade")

        if not store.zip_code:
            missing_data.append("CEP")

        if missing_data:
            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=f"Dados incompletos: {', '.join(missing_data)}"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "incomplete_store_data",
                    "message": "Complete o cadastro da loja para criar assinatura",
                    "missing_fields": missing_data
                }
            )

        # ─────────────────────────────────────────────────────────────────
        # 2. VALIDAÇÃO DE CARTÃO
        # ─────────────────────────────────────────────────────────────────

        if not subscription_data.card or not subscription_data.card.payment_token:
            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error="Cartão não fornecido"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail="Token do cartão é obrigatório"
            )

        # ─────────────────────────────────────────────────────────────────
        # 3. VERIFICAÇÃO DE ASSINATURA EXISTENTE
        # ─────────────────────────────────────────────────────────────────

        existing_sub = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store.id
        ).order_by(models.StoreSubscription.id.desc()).first()

        # ❌ Já tem TRIAL ativo? NÃO PODE
        if existing_sub and existing_sub.status == 'trial':
            if _has_days_remaining(existing_sub.current_period_end):
                audit.log_failed_action(
                    action=AuditAction.CREATE_SUBSCRIPTION,
                    entity_type=AuditEntityType.SUBSCRIPTION,
                    error="Tentativa de criar assinatura com TRIAL ativo"
                )
                db.commit()

                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "trial_still_active",
                        "message": "Seu período de teste ainda está ativo",
                        "action": "Complete o TRIAL ou aguarde expirar"
                    }
                )

        # ❌ Já tem ACTIVE? NÃO PODE
        if existing_sub and existing_sub.status == 'active':
            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error="Tentativa de criar assinatura com ACTIVE existente"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "subscription_already_active",
                    "message": "Você já possui uma assinatura ativa"
                }
            )

        # ─────────────────────────────────────────────────────────────────
        # 4. CRIAR CUSTOMER NO PAGAR.ME (se não existe)
        # ─────────────────────────────────────────────────────────────────

        if not store.pagarme_customer_id:
            logger.info(f"Criando customer no Pagar.me...")

            customer_resp = pagarme_service.create_customer(
                email=user.email,
                name=user.name or store.name,
                document=store.cnpj or user.cpf,
                phone=store.phone or user.phone,
                store_id=store.id
            )

            store.pagarme_customer_id = customer_resp["id"]
            logger.info(f"✅ Customer criado: {store.pagarme_customer_id}")

        # ─────────────────────────────────────────────────────────────────
        # 5. ADICIONAR CARTÃO
        # ─────────────────────────────────────────────────────────────────

        billing_address = {
            "line_1": f"{store.street}, {store.number}",
            "line_2": store.complement if store.complement else None,
            "zip_code": "".join(filter(str.isdigit, store.zip_code)),
            "city": store.city,
            "state": store.state[:2].upper(),
            "country": "BR"
        }

        billing_address = {k: v for k, v in billing_address.items() if v}

        try:
            card_resp = pagarme_service.create_card(
                customer_id=store.pagarme_customer_id,
                card_token=subscription_data.card.payment_token,
                billing_address=billing_address
            )

            store.pagarme_card_id = card_resp["id"]
            logger.info(f"✅ Cartão adicionado: {card_resp['id']}")

        except PagarmeError as e:
            audit.log_failed_action(
                action=AuditAction.CREATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=f"Erro ao adicionar cartão: {str(e)}"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "card_declined",
                    "message": "Cartão recusado. Verifique e tente novamente.",
                    "details": str(e)
                }
            )

        # ─────────────────────────────────────────────────────────────────
        # 6. CRIAR OU REUTILIZAR ASSINATURA
        # ─────────────────────────────────────────────────────────────────

        if existing_sub and existing_sub.status in ['trial', 'canceled', 'expired']:
            subscription = existing_sub
            logger.info(f"♻️ Reutilizando assinatura: {subscription.id}")
        else:
            main_plan = db.query(models.Plans).filter_by(
                plan_name='Plano Parceiro'
            ).first()

            if not main_plan:
                raise HTTPException(
                    status_code=500,
                    detail="Erro de configuração: Plano não encontrado"
                )

            subscription = models.StoreSubscription(
                store=store,
                plan=main_plan,
                status="expired",
                current_period_start=datetime.now(timezone.utc) - timedelta(days=1),
                current_period_end=datetime.now(timezone.utc),
            )

            db.add(subscription)
            db.flush()

            logger.info(f"✨ Nova assinatura criada: {subscription.id}")

        # ─────────────────────────────────────────────────────────────────
        # 7. ATIVAR ASSINATURA
        # ─────────────────────────────────────────────────────────────────

        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=30)

        subscription.status = "active"
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.canceled_at = None

        logger.info(f"✅ Status: EXPIRED → ACTIVE")
        logger.info(f"   Período: {now.date()} → {period_end.date()}")

        # ─────────────────────────────────────────────────────────────────
        # 8. LOG E EMISSÃO DE EVENTOS
        # ─────────────────────────────────────────────────────────────────

        audit.log(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            changes={
                "plan": subscription.plan.plan_name,
                "status": "active",
                "period_start": now.isoformat(),
                "period_end": period_end.isoformat(),
                "charged": True,
                "amount": float(subscription.plan.minimum_fee) / 100
            }
        )

        db.commit()

        # ✅ 1. Emitir para a sala pessoal do admin (subscription_updated)
        store_accesses = db.query(models.StoreAccess).filter(
            models.StoreAccess.store_id == store.id
        ).all()

        for access in store_accesses:
            admin_id = access.user_id
            notification_room = f"admin_notifications_{admin_id}"

            await sio.emit(
                'subscription_updated',
                {
                    'store_id': store.id,
                    'store_name': store.name,
                    'is_blocked': False,
                    'status': 'active',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                },
                to=notification_room,
                namespace='/admin'
            )

        logger.info(f"✅ Emitido 'subscription_updated' para {len(store_accesses)} admin(s)")

        # ✅ 2. NOVO: Emitir LISTA COMPLETA ATUALIZADA para cada admin
        for access in store_accesses:
            admin_id = access.user_id

            # Busca todas as lojas do admin (novamente, para pegar dados atualizados)
            accessible_store_accesses = StoreAccessService.get_accessible_stores_with_roles(
                db,
                db.query(models.User).filter(models.User.id == admin_id).first()
            )

            # Prepara a lista completa de lojas
            stores_list_payload = []
            for store_access in accessible_store_accesses:
                store_dict = StoreService.get_store_complete_payload(
                    store=store_access.store,
                    db=db
                )

                access_dict = {
                    'store': store_dict,
                    'role': store_access.role,
                    'store_id': store_access.store_id,
                    'user_id': store_access.user_id,
                }

                from src.api.schemas.store.store_with_role import StoreWithRole
                store_with_role = StoreWithRole.model_validate(access_dict)
                stores_list_payload.append(store_with_role.model_dump(mode='json'))

            # Emite a lista COMPLETA atualizada
            await sio.emit(
                'admin_stores_list',
                {"stores": stores_list_payload},
                to=f"admin_notifications_{admin_id}",
                namespace='/admin'
            )

            logger.info(f"✅ Emitido 'admin_stores_list' atualizada para admin {admin_id}")

        await admin_emit_store_updated(db, store.id)
        await emit_store_updated(db, store.id)

        logger.info(f"✅ Assinatura {subscription.id} ativada com sucesso!")

        return {
            "status": "success",
            "message": "Assinatura ativada com sucesso!",
            "subscription": {
                "id": subscription.id,
                "status": "active",
                "current_period_start": now.isoformat(),
                "current_period_end": period_end.isoformat(),
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        audit.log_failed_action(
            action=AuditAction.CREATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro crítico: {str(e)}"
        )
        db.commit()

        logger.error(f"❌ Erro ao criar assinatura: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Erro ao processar assinatura. Tente novamente."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ♻️ ENDPOINT 2: REATIVAR ASSINATURA (CANCELED + DIAS → ACTIVE)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/stores/{store_id}/subscriptions/reactivate")
async def reactivate_subscription(
        request: Request,
        db: GetDBDep,
        store: GetStoreForSubscriptionDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
):
    """
    ✅ Reativa assinatura cancelada (SEM cobrar se ainda tem dias)

    Validações:
    - Assinatura existe
    - Status é CANCELED
    - Ainda tem dias restantes

    Lógica:
    - CANCELED + dias → Status CANCELED → ACTIVE
    - SEM dias → Erro (use criar nova)
    """

    logger.info(f"🔄 Reativando assinatura para loja {store.id}...")

    try:
        subscription = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store.id
        ).order_by(models.StoreSubscription.id.desc()).first()

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma assinatura encontrada"
            )

        # ✅ Só pode reativar se status é CANCELED
        if subscription.status != 'canceled':
            audit.log_failed_action(
                action=AuditAction.REACTIVATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=f"Status inválido para reativação: {subscription.status}"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_status",
                    "message": f"Não é possível reativar com status '{subscription.status}'"
                }
            )

        # ✅ Verifica se ainda tem dias
        if not _has_days_remaining(subscription.current_period_end):
            audit.log_failed_action(
                action=AuditAction.REACTIVATE_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error="Tentativa de reativar sem dias restantes"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "no_days_remaining",
                    "message": "Seu período pago expirou. Use o pagamento para criar nova assinatura.",
                    "action": "POST /stores/{id}/subscriptions"
                }
            )

        # ─────────────────────────────────────────────────────────────────
        # REATIVAR
        # ─────────────────────────────────────────────────────────────────

        days_remaining = _get_days_remaining(subscription.current_period_end)

        subscription.status = "active"
        subscription.canceled_at = None

        logger.info(f"✅ Status: CANCELED → ACTIVE")
        logger.info(f"   Dias restantes: {days_remaining}")

        audit.log(
            action=AuditAction.REACTIVATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            changes={
                "status": "active",
                "days_remaining": days_remaining,
                "access_until": subscription.current_period_end.isoformat(),
                "charged": False,
                "charge_amount": 0
            }
        )

        db.commit()

        await admin_emit_store_updated(db, store.id)
        await emit_store_updated(db, store.id)

        logger.info(f"✅ Assinatura reativada: {subscription.id}")

        return {
            "status": "success",
            "message": f"Assinatura reativada! Você tem {days_remaining} dias restantes.",
            "subscription": {
                "id": subscription.id,
                "status": "active",
                "access_until": subscription.current_period_end.isoformat(),
                "days_remaining": days_remaining
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        audit.log_failed_action(
            action=AuditAction.REACTIVATE_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro crítico: {str(e)}"
        )
        db.commit()

        logger.error(f"❌ Erro ao reativar: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Erro ao reativar assinatura. Tente novamente."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ⏸️ ENDPOINT 3: CANCELAR ASSINATURA (ACTIVE/TRIAL → CANCELED)
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/stores/{store_id}/subscriptions")
async def cancel_subscription(
        request: Request,
        db: GetDBDep,
        store: GetStoreForSubscriptionDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
):
    """
    ✅ Cancela assinatura (MAS NÃO BLOQUEIA)

    Validações:
    - Assinatura existe
    - Status é ACTIVE ou TRIAL

    Comportamento:
    - Status: ACTIVE/TRIAL → CANCELED
    - Salva canceled_at
    - NÃO fecha loja imediatamente
    - NÃO desconecta chatbot
    - Usuário continua com acesso até fim do período
    - Job automático bloqueia no último dia
    """

    logger.info(f"🔴 Cancelando assinatura para loja {store.id}...")

    try:
        subscription = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store.id
        ).order_by(models.StoreSubscription.id.desc()).first()

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma assinatura encontrada"
            )

        # ❌ Só pode cancelar se ACTIVE ou TRIAL
        if subscription.status not in ['active', 'trialing']:
            audit.log_failed_action(
                action=AuditAction.CANCEL_SUBSCRIPTION,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=f"Tentativa de cancelar com status: {subscription.status}"
            )
            db.commit()

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_status",
                    "message": f"Não é possível cancelar com status '{subscription.status}'"
                }
            )

        # ─────────────────────────────────────────────────────────────────
        # CANCELAR
        # ─────────────────────────────────────────────────────────────────

        old_status = subscription.status
        now = datetime.now(timezone.utc)

        subscription.status = "canceled"
        subscription.canceled_at = now

        end_date = _normalize_datetime(subscription.current_period_end)
        days_remaining = _get_days_remaining(subscription.current_period_end)

        logger.info(f"✅ Status: {old_status} → CANCELED")
        logger.info(f"   Cancelado em: {now.isoformat()}")
        logger.info(f"   Dias restantes: {days_remaining}")
        logger.info(f"   Acesso até: {end_date.date() if end_date else 'N/A'}")

        audit.log(
            action=AuditAction.CANCEL_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            entity_id=subscription.id,
            changes={
                "old_status": old_status,
                "new_status": "canceled",
                "canceled_at": now.isoformat(),
                "access_until": end_date.isoformat() if end_date else None,
                "days_remaining": days_remaining
            }
        )

        db.commit()

        await admin_emit_store_updated(db, store.id)
        await emit_store_updated(db, store.id)

        logger.info(f"✅ Assinatura cancelada: {subscription.id}")

        return {
            "status": "success",
            "message": (
                f"Assinatura cancelada com sucesso.\n\n"
                f"Você manterá acesso COMPLETO até {end_date.strftime('%d/%m/%Y') if end_date else 'indefinidamente'} "
                f"({days_remaining} dias).\n\n"
                f"Isso inclui:\n"
                f"• Chatbot ativo\n"
                f"• Loja aberta\n"
                f"• Acesso ao painel\n\n"
                f"Pode reativar a qualquer momento antes dessa data."
            ),
            "canceled_at": now.isoformat(),
            "access_until": end_date.isoformat() if end_date else None,
            "days_remaining": days_remaining,
            "blocked_date": (end_date + timedelta(days=3)).isoformat() if end_date else None
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        audit.log_failed_action(
            action=AuditAction.CANCEL_SUBSCRIPTION,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro crítico: {str(e)}"
        )
        db.commit()

        logger.error(f"❌ Erro ao cancelar: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Erro ao cancelar assinatura. Tente novamente."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 📋 ENDPOINT 4: OBTER DETALHES DA ASSINATURA (read-only)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/stores/{store_id}/subscriptions/details")
async def get_subscription_details(
        db: GetDBDep,
        store: GetStoreForSubscriptionDep,
        user: GetCurrentUserDep,
):
    """
    ✅ Retorna detalhes enriquecidos da assinatura

    Sem auditoria (apenas leitura)
    Estados derivados calculados em tempo real
    """

    details = SubscriptionService.get_enriched_subscription(
        store=store,
        db=db,
    )

    if not details:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma assinatura encontrada"
        )

    return details


# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINT 5: ATUALIZAR CARTÃO
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/stores/{store_id}/subscriptions/card")
async def update_subscription_card(
        request: Request,
        db: GetDBDep,
        store: GetStoreForSubscriptionDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
        card_data: CreateStoreSubscription,
):
    """
    ✅ Atualiza cartão da assinatura (SEM cobrar)

    Validações:
    - Assinatura está ACTIVE
    - Cartão válido

    Comportamento:
    - Substitui cartão antigo
    - Mantém assinatura ativa
    - Sem cobranças
    """

    logger.info(f"🔄 Atualizando cartão para loja {store.id}...")

    try:
        subscription = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store.id,
            models.StoreSubscription.status.in_(['active', 'trialing'])
        ).first()

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma assinatura ativa encontrada"
            )

        if not card_data.card or not card_data.card.payment_token:
            raise HTTPException(
                status_code=400,
                detail="Token do cartão é obrigatório"
            )

        # ─────────────────────────────────────────────────────────────────
        # ADICIONAR NOVO CARTÃO
        # ─────────────────────────────────────────────────────────────────

        billing_address = {
            "line_1": f"{store.street}, {store.number}",
            "zip_code": "".join(filter(str.isdigit, store.zip_code)),
            "city": store.city,
            "state": store.state[:2].upper(),
            "country": "BR"
        }

        try:
            card_resp = pagarme_service.create_card(
                customer_id=store.pagarme_customer_id,
                card_token=card_data.card.payment_token,
                billing_address=billing_address
            )

            old_card_id = store.pagarme_card_id
            store.pagarme_card_id = card_resp["id"]

            logger.info(f"✅ Cartão atualizado: {old_card_id} → {card_resp['id']}")

            audit.log(
                action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
                entity_type=AuditEntityType.SUBSCRIPTION,
                entity_id=subscription.id,
                changes={
                    "old_card_id": old_card_id,
                    "new_card_id": card_resp["id"],
                    "brand": card_resp.get("brand")
                }
            )

            db.commit()

            await admin_emit_store_updated(db, store.id)
            await emit_store_updated(db, store.id)

            return {
                "status": "success",
                "message": "Cartão atualizado com sucesso!",
                "card": {
                    "id": card_resp["id"],
                    "brand": card_resp.get("brand"),
                    "last_four": card_resp.get("last_four_digits")
                }
            }

        except PagarmeError as e:
            audit.log_failed_action(
                action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
                entity_type=AuditEntityType.SUBSCRIPTION,
                error=str(e)
            )
            db.commit()

            raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        audit.log_failed_action(
            action=AuditAction.UPDATE_SUBSCRIPTION_CARD,
            entity_type=AuditEntityType.SUBSCRIPTION,
            error=f"Erro crítico: {str(e)}"
        )
        db.commit()

        logger.error(f"❌ Erro ao atualizar cartão: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar cartão. Tente novamente."
        )