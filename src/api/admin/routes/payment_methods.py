from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import joinedload

from src.api.admin.socketio.emitters import admin_emit_store_updated, admin_emit_store_full_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
# Importe seus novos modelos e schemas
from src.core import models
from src.core.database import GetDBDep
from src.api.schemas.payment_method import PaymentMethodGroupOut, \
 \
    PaymentMethodCategoryOut, PlatformPaymentMethodOut, StorePaymentMethodActivationOut

...

router = APIRouter(
    tags=["Payment Methods Config"],
    prefix="/stores/{store_id}/payment-methods"
)


# --- NOVO SCHEMA para receber os dados de ativação ---
class ActivationUpdateSchema(BaseModel):
    is_active: bool
    fee_percentage: float = 0.0
    details: dict | None = None
    is_for_delivery: bool
    is_for_pickup: bool
    is_for_in_store: bool


# ────────────────  1. LISTAR TODOS OS MÉTODOS E SUAS ATIVAÇÕES  ────────────────
@router.get("", response_model=list[PaymentMethodGroupOut])
def list_all_payment_methods_for_store(db: GetDBDep, store_id: int):
    # ✅ CORREÇÃO: Adicionamos .join() para que o .order_by() funcione
    all_platform_methods = db.query(models.PlatformPaymentMethod).options(
        # O joinedload continua aqui para garantir que os objetos venham completos
        joinedload(models.PlatformPaymentMethod.category)
        .joinedload(models.PaymentMethodCategory.group)
    ).join(
        models.PaymentMethodCategory,
        models.PlatformPaymentMethod.category_id == models.PaymentMethodCategory.id
    ).join(
        models.PaymentMethodGroup,
        models.PaymentMethodCategory.group_id == models.PaymentMethodGroup.id
    ).order_by(
        models.PaymentMethodGroup.priority,
        models.PaymentMethodCategory.priority,
        models.PlatformPaymentMethod.name
    ).all()

    # 2. Pega as ativações específicas desta loja em um mapa para acesso rápido
    store_activations = db.query(models.StorePaymentMethodActivation).filter(
        models.StorePaymentMethodActivation.store_id == store_id
    ).all()
    activations_map = {act.platform_payment_method_id: act for act in store_activations}

    # 3. Combina e estrutura os dados (Lógica de Agrupamento)
    groups_map = {}
    for method in all_platform_methods:
        group = groups_map.setdefault(
            method.category.group.name,
            PaymentMethodGroupOut(name=method.category.group.name, categories=[])
        )

        category = next((c for c in group.categories if c.name == method.category.name), None)
        if not category:
            category = PaymentMethodCategoryOut(name=method.category.name, methods=[])
            group.categories.append(category)

        method_out = PlatformPaymentMethodOut.model_validate(method)

        # Anexa a ativação da loja ao método, se existir
        if method.id in activations_map:
            method_out.activation = StorePaymentMethodActivationOut.model_validate(activations_map[method.id])

        category.methods.append(method_out)

    return list(groups_map.values())


# ────────────────  2. ATIVAR/DESATIVAR/CONFIGURAR UM MÉTODO  ────────────────
@router.patch("/{platform_method_id}/activation", response_model=StorePaymentMethodActivationOut)
async def activate_or_configure_method(
        db: GetDBDep,
        store_id: int,
        platform_method_id: int,
        data: ActivationUpdateSchema
):
    # Procura pela ativação existente
    activation = db.query(models.StorePaymentMethodActivation).filter(
        models.StorePaymentMethodActivation.store_id == store_id,
        models.StorePaymentMethodActivation.platform_payment_method_id == platform_method_id
    ).first()

    if not activation:
        # Se não existe, cria uma nova
        activation = models.StorePaymentMethodActivation(
            store_id=store_id,
            platform_payment_method_id=platform_method_id
        )
        db.add(activation)

    # Atualiza os dados
    activation.is_active = data.is_active
    activation.fee_percentage = data.fee_percentage
    activation.details = data.details
    activation.is_for_delivery = data.is_for_delivery
    activation.is_for_pickup = data.is_for_pickup
    activation.is_for_in_store = data.is_for_in_store

    db.commit()
    db.refresh(activation)

    # TODO: Emitir um evento de socket para notificar a UI da mudança
    await emit_store_updated(db, store_id)
    await admin_emit_store_updated(db, store_id)
    return activation