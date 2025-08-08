# Em: src/api/customer/routes/loyalty_routes.py

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from src.api.shared_schemas.coupon import CouponOut
from src.core.database import GetDBDep
from src.api.admin.services import loyalty_service  # Reutilizamos o mesmo serviço
from src.api.admin.schemas.loyalty_schema import CustomerLoyaltyDashboardSchema
# Importe sua dependência para pegar o cliente logado
# from src.api.customer.dependencies import get_current_customer
from src.core import models
from src.core.dependencies import GetStoreDep

router = APIRouter(prefix="/loyalty", tags=["Customer Loyalty"])


@router.get("/store/{store_id}", response_model=CustomerLoyaltyDashboardSchema)
def get_my_loyalty_dashboard_for_store(
        store_id: int,
        db: GetDBDep,
        # Descomente e ajuste para sua dependência de cliente
        # current_customer: models.Customer = Depends(get_current_customer)
):
    """Retorna o dashboard de fidelidade do cliente logado para uma loja específica."""
    # Apenas como exemplo, usando um ID fixo. Substitua pelo ID do cliente logado.
    customer_id_example = 1

    return loyalty_service.get_customer_dashboard(
        db=db,
        customer_id=customer_id_example,  # Substitua por current_customer.id
        store_id=store_id
    )


@router.post(
    "/rewards/{reward_id}/claim",
    response_model=CouponOut,
    summary="Resgatar um prêmio de fidelidade desbloqueado"
)
def claim_loyalty_reward(
    reward_id: int,
    customer_id: int,  # Vem da query string: ?customer_id=123
    db: GetDBDep,
    store: GetStoreDep,
):
    """
    Verifica se o cliente pode resgatar um prêmio e, se puder,
    gera um cupom de uso único para o produto do prêmio.
    """
    try:
        generated_coupon = loyalty_service.claim_reward(
            db=db,
            customer_id=customer_id,
            store_id=store.id,
            reward_id=reward_id
        )
        return generated_coupon
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
