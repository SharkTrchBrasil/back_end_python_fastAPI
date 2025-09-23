# src/api/routers/review.py
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas.store.review import ReviewCreate
from src.core.database import GetDBDep
from src.core import models
from src.core.dependencies import get_current_customer_dep

router = APIRouter(tags=["Reviews"], prefix="/reviews")

@router.post("/order/{public_id}", status_code=201)
def submit_order_review(
    public_id: str,
    review_in: ReviewCreate,
    db: GetDBDep,
    current_customer: models.Customer = Depends(get_current_customer_dep)
):
    # 1. Encontra o pedido, garantindo que ele pertence ao cliente logado
    order = db.query(models.Order).filter(
        models.Order.public_id == public_id,
        models.Order.customer_id == current_customer.id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado ou não pertence a este cliente.")

    if order.order_status != models.OrderStatus.DELIVERED and order.order_status != models.OrderStatus.FINALIZED:
         raise HTTPException(status_code=400, detail="Você só pode avaliar pedidos que já foram entregues.")

    # 2. Verifica se uma avaliação para este pedido já existe
    existing_review = db.query(models.StoreRating).filter_by(order_id=order.id).first()
    if existing_review:
        raise HTTPException(status_code=400, detail="Você já avaliou este pedido.")

    # 3. Cria o novo registro de avaliação da loja
    new_review = models.StoreRating(
        stars=review_in.stars,
        comment=review_in.comment,
        customer_id=current_customer.id,
        order_id=order.id,
        store_id=order.store_id
    )

    db.add(new_review)
    db.commit()

    # Opcional: Recalcular a média de avaliações da loja aqui

    return {"message": "Avaliação recebida com sucesso. Obrigado!"}