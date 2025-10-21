# src/api/admin/routes/coupons.py

import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import selectinload

from src.api.admin.services.coupon_notification_service import send_coupon_notification_task
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.financial.coupon import CouponCreate, CouponUpdate, CouponOut
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.utils.enums import AuditAction, AuditEntityType

router = APIRouter(tags=["Coupons"], prefix="/stores/{store_id}/coupons")


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 1: CRIAR CUPOM
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=CouponOut, status_code=201)
async def create_coupon(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
        coupon_data: CouponCreate,
        background_tasks: BackgroundTasks,
):
    """
    ✅ Cria um novo cupom de desconto com auditoria completa

    - Valida código único
    - Cria regras de aplicação
    - Opcionalmente notifica clientes via WhatsApp
    """

    # ═══════════════════════════════════════════════════════════
    # 1. VALIDAÇÃO DE CÓDIGO ÚNICO
    # ═══════════════════════════════════════════════════════════

    existing_coupon = db.query(models.Coupon).filter(
        models.Coupon.code == coupon_data.code.upper(),
        models.Coupon.store_id == store.id,
    ).first()

    if existing_coupon:
        # ✅ LOG DE TENTATIVA FALHADA
        audit.log_failed_action(
            action=AuditAction.CREATE_COUPON,
            entity_type=AuditEntityType.COUPON,
            error=f"Código duplicado: {coupon_data.code}"
        )
        db.commit()

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Um cupom com este código já existe para esta loja.",
                "code": "CODE_ALREADY_EXISTS"
            }
        )

    # ═══════════════════════════════════════════════════════════
    # 2. CRIAÇÃO DO CUPOM COM REGRAS
    # ═══════════════════════════════════════════════════════════

    db_coupon = models.Coupon(
        **coupon_data.model_dump(exclude={'rules'}),
        store_id=store.id,
    )

    # Anexa as regras (cascade vai salvar automaticamente)
    for rule_schema in coupon_data.rules:
        new_rule = models.CouponRule(
            rule_type=rule_schema.rule_type,
            value=rule_schema.value
        )
        db_coupon.rules.append(new_rule)

    db.add(db_coupon)
    db.flush()  # Para obter o ID antes do commit

    # ═══════════════════════════════════════════════════════════
    # 3. PREPARAÇÃO DE NOTIFICAÇÕES (SE SOLICITADO)
    # ═══════════════════════════════════════════════════════════

    will_notify = coupon_data.notify_customers

    if will_notify:
        db_coupon.whatsapp_notification_status = 'queued'
        background_tasks.add_task(
            send_coupon_notification_task,
            db,
            db_coupon.id,
            store.id
        )

    # ═══════════════════════════════════════════════════════════
    # 4. LOG DE CRIAÇÃO BEM-SUCEDIDA
    # ═══════════════════════════════════════════════════════════

    audit.log(
        action=AuditAction.CREATE_COUPON,
        entity_type=AuditEntityType.COUPON,
        entity_id=db_coupon.id,
        changes={
            "store_name": store.name,
            "coupon_code": db_coupon.code,
            "discount_type": db_coupon.discount_type,
            "discount_value": float(db_coupon.discount_value),
            "min_order_value": float(db_coupon.min_order_value) if db_coupon.min_order_value else None,
            "max_discount": float(db_coupon.max_discount) if db_coupon.max_discount else None,
            "usage_limit": db_coupon.usage_limit,
            "valid_from": db_coupon.valid_from.isoformat() if db_coupon.valid_from else None,
            "valid_until": db_coupon.valid_until.isoformat() if db_coupon.valid_until else None,
            "is_active": db_coupon.is_active,
            "rules_count": len(coupon_data.rules),
            "notify_customers": will_notify
        },
        description=(
            f"Cupom '{db_coupon.code}' criado - "
            f"Desconto: {db_coupon.discount_value}{'%' if db_coupon.discount_type == 'percentage' else ' reais'} - "
            f"{'📱 Notificação agendada' if will_notify else 'Sem notificação'}"
        )
    )

    db.commit()
    db.refresh(db_coupon)

    # Emite eventos de atualização
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return db_coupon


# ═══════════════════════════════════════════════════════════════
# ROTAS DE LEITURA - SEM AUDITORIA
# ═══════════════════════════════════════════════════════════════

@router.get("", response_model=list[CouponOut])
def get_coupons(
        db: GetDBDep,
        store: GetStoreDep,
):
    """Lista todos os cupons da loja."""
    coupons = db.query(models.Coupon).filter(
        models.Coupon.store_id == store.id,
    ).options(
        selectinload(models.Coupon.rules)
    ).order_by(models.Coupon.id.desc()).all()

    return coupons


@router.get("/{coupon_id}", response_model=CouponOut)
def get_coupon(
        db: GetDBDep,
        store: GetStoreDep,
        coupon_id: int
):
    """Busca um cupom específico."""
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id,
    ).options(
        selectinload(models.Coupon.rules)
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    return coupon


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 2: ATUALIZAR CUPOM
# ═══════════════════════════════════════════════════════════════

@router.patch("/{coupon_id}", response_model=CouponOut)
async def patch_coupon(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
        coupon_id: int,
        coupon_update: CouponUpdate,
):
    """
    ✅ Atualiza um cupom existente com auditoria de mudanças

    - Rastreia todas as alterações
    - Pode substituir regras completamente
    - Registra ativação/desativação
    """

    coupon = db.query(models.Coupon).options(
        selectinload(models.Coupon.rules)
    ).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id,
    ).first()

    if not coupon:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.UPDATE_COUPON,
            entity_type=AuditEntityType.COUPON,
            entity_id=coupon_id,
            error="Cupom não encontrado"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Coupon not found")

    # ═══════════════════════════════════════════════════════════
    # 1. CAPTURA ESTADO ANTERIOR
    # ═══════════════════════════════════════════════════════════

    old_values = {
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "is_active": coupon.is_active,
        "min_order_value": float(coupon.min_order_value) if coupon.min_order_value else None,
        "max_discount": float(coupon.max_discount) if coupon.max_discount else None,
        "usage_limit": coupon.usage_limit,
        "valid_from": coupon.valid_from.isoformat() if coupon.valid_from else None,
        "valid_until": coupon.valid_until.isoformat() if coupon.valid_until else None,
        "rules_count": len(coupon.rules)
    }

    # ═══════════════════════════════════════════════════════════
    # 2. APLICA ATUALIZAÇÕES
    # ═══════════════════════════════════════════════════════════

    update_data = coupon_update.model_dump(exclude_unset=True)
    changes = {}

    # Atualiza campos simples
    for field, value in update_data.items():
        if field != 'rules':
            old_val = getattr(coupon, field)
            if old_val != value:
                changes[field] = {
                    "from": old_val,
                    "to": value
                }
            setattr(coupon, field, value)

    # ═══════════════════════════════════════════════════════════
    # 3. ATUALIZA REGRAS (SE FORNECIDAS)
    # ═══════════════════════════════════════════════════════════

    if 'rules' in update_data:
        # Remove regras antigas
        for old_rule in coupon.rules:
            db.delete(old_rule)
        db.flush()

        # Adiciona novas regras
        for rule_schema in coupon_update.rules:
            new_rule = models.CouponRule(
                rule_type=rule_schema.rule_type,
                value=rule_schema.value,
                coupon_id=coupon.id
            )
            db.add(new_rule)

        changes["rules"] = {
            "from": old_values["rules_count"],
            "to": len(coupon_update.rules)
        }

    # ═══════════════════════════════════════════════════════════
    # 4. DETECTA ATIVAÇÃO/DESATIVAÇÃO
    # ═══════════════════════════════════════════════════════════

    status_changed = False
    if "is_active" in changes:
        status_changed = True
        action_type = AuditAction.ACTIVATE_COUPON if coupon.is_active else AuditAction.DEACTIVATE_COUPON

    # ═══════════════════════════════════════════════════════════
    # 5. LOG DE ATUALIZAÇÃO
    # ═══════════════════════════════════════════════════════════

    audit.log(
        action=action_type if status_changed else AuditAction.UPDATE_COUPON,
        entity_type=AuditEntityType.COUPON,
        entity_id=coupon.id,
        changes={
            "store_name": store.name,
            "coupon_code": coupon.code,
            "old_values": old_values,
            "changes": changes,
            "status_changed": status_changed
        },
        description=(
            f"Cupom '{coupon.code}' {'ATIVADO' if status_changed and coupon.is_active else 'DESATIVADO' if status_changed else 'atualizado'} "
            f"por '{user.name}'"
        )
    )

    db.commit()
    db.refresh(coupon)

    # Emite eventos
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return coupon


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 3: DELETAR CUPOM
# ═══════════════════════════════════════════════════════════════

@router.delete("/{coupon_id}", status_code=204)
async def delete_coupon(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
        coupon_id: int
):
    """
    ✅ Deleta um cupom com auditoria

    ⚠️ CUIDADO: Ação irreversível
    """

    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id
    ).first()

    if not coupon:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.DELETE_COUPON,
            entity_type=AuditEntityType.COUPON,
            entity_id=coupon_id,
            error="Cupom não encontrado"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Coupon not found")

    # ═══════════════════════════════════════════════════════════
    # 1. VALIDAÇÃO DE SEGURANÇA (OPCIONAL)
    # ═══════════════════════════════════════════════════════════

    # Verifica se o cupom já foi usado
    # usage_count = db.query(models.Order).filter(
    #     models.Order.coupon_id == coupon_id
    # ).count()

    # if usage_count > 0:
    #     audit.log_failed_action(
    #         action=AuditAction.DELETE_COUPON,
    #         entity_type=AuditEntityType.COUPON,
    #         entity_id=coupon_id,
    #         error=f"Cupom não pode ser deletado - {usage_count} usos registrados"
    #     )
    #     db.commit()
    #
    #     raise HTTPException(
    #         status_code=400,
    #         detail="Cannot delete a coupon that has been used."
    #     )

    # ═══════════════════════════════════════════════════════════
    # 2. CAPTURA DADOS ANTES DE DELETAR
    # ═══════════════════════════════════════════════════════════

    coupon_data = {
        "coupon_id": coupon.id,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "was_active": coupon.is_active,
        "usage_limit": coupon.usage_limit,
        "current_usage": coupon.current_usage,
        "valid_from": coupon.valid_from.isoformat() if coupon.valid_from else None,
        "valid_until": coupon.valid_until.isoformat() if coupon.valid_until else None
    }

    # ═══════════════════════════════════════════════════════════
    # 3. LOG DE DELEÇÃO
    # ═══════════════════════════════════════════════════════════

    audit.log(
        action=AuditAction.DELETE_COUPON,
        entity_type=AuditEntityType.COUPON,
        entity_id=coupon.id,
        changes={
            "deleted_by": user.name,
            "store_name": store.name,
            "coupon_data": coupon_data
        },
        description=f"⚠️ Cupom '{coupon.code}' DELETADO por '{user.name}'"
    )

    # ═══════════════════════════════════════════════════════════
    # 4. EXECUTA DELEÇÃO
    # ═══════════════════════════════════════════════════════════

    db.delete(coupon)
    db.commit()

    # Emite eventos
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return None