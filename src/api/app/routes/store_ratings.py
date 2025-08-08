from fastapi import APIRouter, HTTPException

from src.api.schemas.rating import StoreRatingCreate, RatingOut
from src.core.database import GetDBDep
from src.core.models import StoreRating

router = APIRouter(prefix="/store-ratings", tags=["Avaliações de Lojas"])


@router.post("/", response_model=RatingOut)
def create_store_rating(data: StoreRatingCreate, db: GetDBDep, user_id: int = 1):
    exists = db.query(StoreRating).filter_by(
        customer_id=user_id,
        order_id=data.order_id,
        store_id=data.store_id
    ).first()

    if exists:
        raise HTTPException(status_code=400, detail="Você já avaliou esta loja nesse pedido.")

    new_rating = StoreRating(
        stars=data.stars,
        comment=data.comment,
        customer_id=user_id,
        order_id=data.order_id,
        store_id=data.store_id,
    )

    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)
    return new_rating
