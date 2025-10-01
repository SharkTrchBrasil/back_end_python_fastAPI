from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import joinedload, selectinload
from collections import defaultdict

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.core import models
from src.core.database import GetDBDep
# ✅ Nossos schemas já estão corretos, refletindo a estrutura de 2 níveis
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


# ────────────────  1. LISTAR TODOS OS MÉTODOS (VERSÃO CORRIGIDA)  ────────────────
@router.get("", response_model=list[PaymentMethodGroupOut])
def list_all_payment_methods_for_store(db: GetDBDep, store_id: int):
    """
    Lista todos os métodos de pagamento da plataforma, combinados com as
    configurações de ativação específicas da loja, usando a nova estrutura de 2 níveis.
    """
    # 1. Busca TODOS os métodos de pagamento da plataforma, já com seus grupos.
    #    A ordenação agora é mais simples: por prioridade do grupo e nome do método.
    all_platform_methods = db.query(models.PlatformPaymentMethod).options(
        joinedload(models.PlatformPaymentMethod.group)
    ).join(
        models.PaymentMethodGroup,
        models.PlatformPaymentMethod.group_id == models.PaymentMethodGroup.id
    ).order_by(
        models.PaymentMethodGroup.priority,
        models.PlatformPaymentMethod.name
    ).all()

    # 2. Pega as ativações específicas desta loja em um mapa para acesso rápido (isso continua igual).
    store_activations = db.query(models.StorePaymentMethodActivation).filter(
        models.StorePaymentMethodActivation.store_id == store_id
    ).all()
    activations_map = {act.platform_payment_method_id: act for act in store_activations}

    # 3. Combina e estrutura os dados (Lógica de Agrupamento Simplificada)
    groups_map = defaultdict(list)
    group_models = {}

    for method in all_platform_methods:
        # Converte o método para o schema de saída
        method_out = PlatformPaymentMethodOut.model_validate(method)

        # Anexa a ativação da loja ao método, se existir.
        # Se não existir, o campo 'activation' no frontend será 'null'.
        if method.id in activations_map:
            method_out.activation = StorePaymentMethodActivationOut.model_validate(activations_map[method.id])

        # Agrupa o método de pagamento (já com sua ativação) sob seu grupo pai.
        groups_map[method.group_id].append(method_out)

        # Armazena o modelo do grupo para usar depois, evitando duplicatas
        if method.group_id not in group_models:
            group_models[method.group_id] = method.group

    # 4. Monta a lista final no formato que o frontend espera.
    final_result = []
    # Itera sobre os grupos na ordem de prioridade
    sorted_group_ids = sorted(group_models.keys(), key=lambda gid: group_models[gid].priority)

    for group_id in sorted_group_ids:
        group_model = group_models[group_id]

        group_out = PaymentMethodGroupOut.model_validate(group_model)
        group_out.methods = groups_map[group_id]  # A lista de métodos já está pronta
        final_result.append(group_out)

    return final_result


# ────────────────  2. ATIVAR/CONFIGURAR (SEM ALTERAÇÕES)  ────────────────
@router.patch("/{platform_method_id}/activation", response_model=StorePaymentMethodActivationOut)
async def activate_or_configure_method(
        db: GetDBDep,
        store_id: int,
        platform_method_id: int,
        data: ActivationUpdateSchema
):
    # Esta lógica já estava correta, pois opera diretamente na tabela de ativação.
    activation = db.query(models.StorePaymentMethodActivation).filter(
        models.StorePaymentMethodActivation.store_id == store_id,
        models.StorePaymentMethodActivation.platform_payment_method_id == platform_method_id
    ).first()

    if not activation:
        activation = models.StorePaymentMethodActivation(
            store_id=store_id,
            platform_payment_method_id=platform_method_id
        )
        db.add(activation)

    activation.is_active = data.is_active
    activation.fee_percentage = data.fee_percentage
    activation.details = data.details
    activation.is_for_delivery = data.is_for_delivery
    activation.is_for_pickup = data.is_for_pickup
    activation.is_for_in_store = data.is_for_in_store

    db.commit()
    db.refresh(activation)

    await emit_store_updated(db, store_id)
    await admin_emit_store_updated(db, store_id)
    return activation