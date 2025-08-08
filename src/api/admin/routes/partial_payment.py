# Em: src/api/admin/routes/order_routes.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.api.admin.schemas.order_partial_payment import PartialPaymentResponseSchema, PartialPaymentCreateSchema
from src.api.admin.services import partial_payment_service
from src.core.database import GetDBDep

router = APIRouter(prefix="/admin", tags=["Admin Orders"])

@router.post(
    "/orders/{order_id}/payments",
    response_model=List[PartialPaymentResponseSchema],
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar pagamentos parciais a um pedido"
)
def add_partial_payments_to_order(
    order_id: int,
    payments_data: List[PartialPaymentCreateSchema], # ✅ Usa nosso schema de criação
    db: GetDBDep
):
    """
    Registra um ou mais pagamentos parciais para um pedido existente.
    """
    try:
        # Delega toda a lógica para a função de serviço
        created_payments = partial_payment_service.add_partial_payments(
            db=db,
            order_id=order_id,
            payments_data=payments_data
        )
        return created_payments
    except ValueError as e:
        # Captura erros de lógica de negócio levantados pelo nosso serviço
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Captura outros erros inesperados
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ocorreu um erro interno.")