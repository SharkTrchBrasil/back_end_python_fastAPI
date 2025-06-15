# src/api/routes/ratings.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.shared_schemas.rating import RatingOut, RatingCreate
from src.core.database import GetDBDep
from src.core import models


router = APIRouter(prefix="/ratings", tags=["Avaliações"])

from fastapi import HTTPException, status


@router.post("/", response_model=RatingOut)
def create_rating(data: RatingCreate, db: GetDBDep, user_id: int):  # user_id futuramente do token
    filters = [
        models.Rating.customer_id == user_id,
        models.Rating.order_id == data.order_id,
    ]

    if data.store_id:
        filters.append(models.Rating.store_id == data.store_id)
    elif data.product_id:
        filters.append(models.Rating.product_id == data.product_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário informar store_id ou product_id."
        )

    # Verifica se já existe avaliação para essa combinação
    exists = db.query(models.Rating).filter(*filters).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você já avaliou este item neste pedido."
        )

    new_rating = models.Rating(
        stars=data.stars,
        comment=data.comment,
        customer_id=user_id,
        order_id=data.order_id,
        store_id=data.store_id,
        product_id=data.product_id,
    )

    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)

    return new_rating
