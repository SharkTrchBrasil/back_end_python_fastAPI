# src/api/admin/routes/payment_methods.py

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import joinedload
from collections import defaultdict

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.utils.enums import AuditAction, AuditEntityType
from src.api.schemas.financial.payment_method import (
    PaymentMethodGroupOut,
    PlatformPaymentMethodOut,
    StorePaymentMethodActivationOut
)

router = APIRouter(
    tags=["Payment Methods Config"],
    prefix="/stores/{store_id}/payment-methods"
)


class ActivationUpdateSchema(BaseModel):
    is_active: bool
    fee_percentage: float = 0.0
    details: dict | None = None
    is_for_delivery: bool
    is_for_pickup: bool
    is_for_in_store: bool


# ═══════════════════════════════════════════════════════════════
# ROTA DE LEITURA - SEM AUDITORIA
# ═══════════════════════════════════════════════════════════════

@router.get("", response_model=list[PaymentMethodGroupOut])
def list_all_payment_methods_for_store(db: GetDBDep, store_id: int):
    """
    Lista todos os métodos de pagamento da plataforma, combinados com as
    configurações de ativação específicas da loja.
    """

    # 1. Busca TODOS os métodos de pagamento da plataforma
    all_platform_methods = db.query(models.PlatformPaymentMethod).options(
        joinedload(models.PlatformPaymentMethod.group)
    ).join(
        models.PaymentMethodGroup,
        models.PlatformPaymentMethod.group_id == models.PaymentMethodGroup.id
    ).order_by(
        models.PaymentMethodGroup.priority,
        models.PlatformPaymentMethod.name
    ).all()

    # 2. Pega as ativações específicas desta loja
    store_activations = db.query(models.StorePaymentMethodActivation).filter(
        models.StorePaymentMethodActivation.store_id == store_id
    ).all()

    activations_map = {act.platform_payment_method_id: act for act in store_activations}

    # 3. Estrutura os dados
    groups_map = defaultdict(list)
    group_models = {}

    for method in all_platform_methods:
        method_out = PlatformPaymentMethodOut.model_validate(method)

        # Anexa a ativação da loja ao método
        if method.id in activations_map:
            method_out.activation = StorePaymentMethodActivationOut.model_validate(
                activations_map[method.id]
            )

        groups_map[method.group_id].append(method_out)

        if method.group_id not in group_models:
            group_models[method.group_id] = method.group

    # 4. Monta a lista final
    final_result = []
    sorted_group_ids = sorted(
        group_models.keys(),
        key=lambda gid: group_models[gid].priority
    )

    for group_id in sorted_group_ids:
        group_model = group_models[group_id]
        group_out = PaymentMethodGroupOut.model_validate(group_model)
        group_out.methods = groups_map[group_id]
        final_result.append(group_out)

    return final_result


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL: ATIVAR/CONFIGURAR MÉTODO DE PAGAMENTO
# ═══════════════════════════════════════════════════════════════

@router.patch("/{platform_method_id}/activation", response_model=StorePaymentMethodActivationOut)
async def activate_or_configure_method(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store_id: int,
        platform_method_id: int,
        data: ActivationUpdateSchema,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
):
    """
    ✅ Ativa/desativa ou configura um método de pagamento com auditoria completa

    - Rastreia ativação/desativação
    - Registra mudanças de taxas
    - Monitora disponibilidade por tipo de pedido
    """

    # ═══════════════════════════════════════════════════════════
    # 1. BUSCA OU CRIA ATIVAÇÃO
    # ═══════════════════════════════════════════════════════════

    activation = db.query(models.StorePaymentMethodActivation).filter(
        models.StorePaymentMethodActivation.store_id == store_id,
        models.StorePaymentMethodActivation.platform_payment_method_id == platform_method_id
    ).first()

    # Busca o método de pagamento para o nome
    platform_method = db.query(models.PlatformPaymentMethod).filter(
        models.PlatformPaymentMethod.id == platform_method_id
    ).first()

    if not platform_method:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.UPDATE_PAYMENT_METHODS,
            entity_type=AuditEntityType.PAYMENT_METHOD,
            error=f"Método de pagamento não encontrado: ID {platform_method_id}"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Payment method not found")

    is_new = activation is None

    if not activation:
        activation = models.StorePaymentMethodActivation(
            store_id=store_id,
            platform_payment_method_id=platform_method_id
        )
        db.add(activation)

    # ═══════════════════════════════════════════════════════════
    # 2. CAPTURA ESTADO ANTERIOR
    # ═══════════════════════════════════════════════════════════

    old_values = {
        "is_active": activation.is_active if not is_new else False,
        "fee_percentage": float(activation.fee_percentage) if not is_new else 0.0,
        "is_for_delivery": activation.is_for_delivery if not is_new else False,
        "is_for_pickup": activation.is_for_pickup if not is_new else False,
        "is_for_in_store": activation.is_for_in_store if not is_new else False
    }

    # ═══════════════════════════════════════════════════════════
    # 3. APLICA ATUALIZAÇÕES
    # ═══════════════════════════════════════════════════════════

    activation.is_active = data.is_active
    activation.fee_percentage = data.fee_percentage
    activation.details = data.details
    activation.is_for_delivery = data.is_for_delivery
    activation.is_for_pickup = data.is_for_pickup
    activation.is_for_in_store = data.is_for_in_store

    db.flush()  # Para obter o ID se for novo

    # ═══════════════════════════════════════════════════════════
    # 4. DETECTA TIPO DE MUDANÇA
    # ═══════════════════════════════════════════════════════════

    changes = {}
    action_type = AuditAction.UPDATE_PAYMENT_METHOD_CONFIG

    if old_values["is_active"] != data.is_active:
        action_type = AuditAction.ACTIVATE_PAYMENT_METHOD if data.is_active else AuditAction.DEACTIVATE_PAYMENT_METHOD
        changes["status_change"] = {
            "from": "active" if old_values["is_active"] else "inactive",
            "to": "active" if data.is_active else "inactive"
        }

    if old_values["fee_percentage"] != data.fee_percentage:
        changes["fee_change"] = {
            "from": old_values["fee_percentage"],
            "to": float(data.fee_percentage)
        }

    if (old_values["is_for_delivery"] != data.is_for_delivery or
            old_values["is_for_pickup"] != data.is_for_pickup or
            old_values["is_for_in_store"] != data.is_for_in_store):
        changes["availability_change"] = {
            "from": {
                "delivery": old_values["is_for_delivery"],
                "pickup": old_values["is_for_pickup"],
                "in_store": old_values["is_for_in_store"]
            },
            "to": {
                "delivery": data.is_for_delivery,
                "pickup": data.is_for_pickup,
                "in_store": data.is_for_in_store
            }
        }

    # ═══════════════════════════════════════════════════════════
    # 5. LOG DE CONFIGURAÇÃO
    # ═══════════════════════════════════════════════════════════

    # Busca informações da loja
    store = db.query(models.Store).filter(models.Store.id == store_id).first()

    audit.log(
        action=action_type,
        entity_type=AuditEntityType.PAYMENT_METHOD,
        entity_id=activation.id,
        changes={
            "store_name": store.name if store else f"Store #{store_id}",
            "payment_method": platform_method.name,
            "is_new": is_new,
            "old_values": old_values,
            "new_values": {
                "is_active": data.is_active,
                "fee_percentage": float(data.fee_percentage),
                "is_for_delivery": data.is_for_delivery,
                "is_for_pickup": data.is_for_pickup,
                "is_for_in_store": data.is_for_in_store
            },
            "changes": changes
        },
        description=(
            f"Método '{platform_method.name}' "
            f"{'ATIVADO' if action_type == AuditAction.ACTIVATE_PAYMENT_METHOD else 'DESATIVADO' if action_type == AuditAction.DEACTIVATE_PAYMENT_METHOD else 'configurado'} "
            f"{'com taxa de ' + str(data.fee_percentage) + '%' if data.fee_percentage > 0 else ''}"
        )
    )

    db.commit()
    db.refresh(activation)

    # ═══════════════════════════════════════════════════════════
    # 6. EMITE EVENTOS (CRÍTICO PARA SINCRONIZAÇÃO)
    # ═══════════════════════════════════════════════════════════

    await emit_store_updated(db, store_id)
    await admin_emit_store_updated(db, store_id)

    return activation