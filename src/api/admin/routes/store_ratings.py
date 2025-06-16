from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.api.shared_schemas.rating import StoreRatingCreate, RatingOut
from src.core.database import GetDBDep
from src.core.models import StoreRating, ProductRating

router = APIRouter(prefix="/stores/{store_id}/store-ratings", tags=["Avaliações de Lojas"])




@router.get("", response_model=List[RatingOut])
def list_store_ratings(store_id: int, db: GetDBDep):
    ratings = db.query(StoreRating).filter_by(store_id=store_id).order_by(StoreRating.created_at.desc()).all()
    return ratings


@router.put("/{rating_id}/reply", response_model=RatingOut)
def reply_to_store_rating(rating_id: int, reply: str, db: GetDBDep):
    rating = db.query(StoreRating).filter_by(id=rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")

    rating.owner_reply = reply
    db.commit()
    db.refresh(rating)
    return rating

@router.get("/product/{product_id}", response_model=List[RatingOut])
def list_product_ratings(product_id: int, db: GetDBDep):
    ratings = db.query(ProductRating).filter_by(product_id=product_id).order_by(ProductRating.created_at.desc()).all()
    return ratings


@router.put("/{rating_id}/reply", response_model=RatingOut)
def reply_to_product_rating(rating_id: int, reply: str, db: GetDBDep):
    rating = db.query(ProductRating).filter_by(id=rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")

    rating.owner_reply = reply
    db.commit()
    db.refresh(rating)
    return rating