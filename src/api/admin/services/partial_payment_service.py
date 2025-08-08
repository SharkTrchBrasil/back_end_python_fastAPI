# Em: src/api/admin/services/order_service.py

from sqlalchemy.orm import Session
from typing import List

# ✅ Importe os schemas necessários
from src.api.admin.schemas.order_partial_payment import PartialPaymentCreateSchema, PartialPaymentResponseSchema
from src.core import models


# ✅ A função agora retorna uma lista do nosso schema de resposta
def add_partial_payments(
        db: Session,
        order_id: int,
        payments_data: List[PartialPaymentCreateSchema]
) -> List[PartialPaymentResponseSchema]:
    """
    Adiciona pagamentos parciais a um pedido, validando as regras de negócio.
    """
    # 1. Buscar o pedido no banco de dados (sem alterações)
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise ValueError(f"Pedido com ID {order_id} não encontrado.")

    # 2. Validar a regra de negócio (sem alterações)
    total_new_payment_amount = sum(p.amount for p in payments_data)
    total_existing_payment_amount = sum(p.amount for p in order.partial_payments)
    if (total_existing_payment_amount + total_new_payment_amount) > order.discounted_total_price:
        raise ValueError("A soma dos pagamentos não pode ultrapassar o valor total do pedido.")

    # 3. Criar os objetos de pagamento parcial (sem alterações)
    created_payments = []
    for payment_data in payments_data:
        new_payment = models.OrderPartialPayment(
            order_id=order_id,
            store_payment_method_activation_id=payment_data.store_payment_method_activation_id,
            amount=payment_data.amount,
            received_by=payment_data.received_by,
            transaction_id=payment_data.transaction_id,
            notes=payment_data.notes
        )
        db.add(new_payment)
        created_payments.append(new_payment)

    # 4. Salvar tudo no banco de dados (sem alterações)
    db.commit()

    # 5. Atualizar os objetos para pegar os IDs e timestamps (sem alterações)
    for payment in created_payments:
        db.refresh(payment)

    # ✅ --- 6. MONTAR A RESPOSTA FINAL (A PARTE OTIMIZADA) ---
    # Em vez de modificar o objeto do banco, criamos o objeto de resposta (Schema)
    # que será enviado como JSON.
    response_data = []
    for payment in created_payments:
        # FastAPI usará o `from_attributes = True` (ou `orm_mode`) para ler os dados
        # e preencher o schema de resposta automaticamente.
        # Acessar a relação aqui carrega os dados necessários.
        response_data.append(
            PartialPaymentResponseSchema(
                id=payment.id,
                amount=payment.amount,
                payment_method_name=payment.payment_method_activation.platform_method.name,
                received_by=payment.received_by,
                transaction_id=payment.transaction_id,
                notes=payment.notes,
                created_at=payment.created_at
            )
        )

    return response_data