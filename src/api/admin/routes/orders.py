from fastapi import APIRouter

from src.api.admin.schemas.order import Order, OrderDetails
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from fastapi import HTTPException, status
router = APIRouter(tags=["Orders"], prefix="/stores/{store_id}/orders")

@router.get("", response_model=list[Order])
def get_orders(
        db: GetDBDep,
        store: GetStoreDep,
):
    return db.query(models.Order).filter_by(store_id=store.id).all()




@router.get("/{order_id}", response_model=OrderDetails)
def get_order(
        db: GetDBDep,
        store: GetStoreDep,
        order_id: int,
):
    order = db.query(models.Order).filter_by(store_id=store.id, id=order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido não encontrado"
        )

    return order
