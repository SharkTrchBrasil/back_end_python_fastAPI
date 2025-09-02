from fastapi import APIRouter, HTTPException

from src.api.schemas.products.rating import ProductRatingCreate, RatingOut
from src.core.database import GetDBDep
from src.core.models import ProductRating

router = APIRouter(prefix="/product-ratings", tags=["Avaliações de Produtos"])


@router.post("/", response_model=RatingOut)
def create_product_rating(data: ProductRatingCreate, db: GetDBDep, user_id: int = 1):
    exists = db.query(ProductRating).filter_by(
        customer_id=user_id,
        order_id=data.order_id,
        product_id=data.product_id
    ).first()

    if exists:
        raise HTTPException(status_code=400, detail="Você já avaliou este produto nesse pedido.")

    new_rating = ProductRating(
        stars=data.stars,
        comment=data.comment,
        customer_id=user_id,
        order_id=data.order_id,
        product_id=data.product_id,
    )

    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)
    return new_rating

