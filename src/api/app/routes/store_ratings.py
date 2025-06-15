from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.shared_schemas.store_ratings import StoreRatingOut, StoreRatingCreate
from src.core.database import GetDBDep
from src.core.models import StoreRating

router = APIRouter(prefix="/stores/{store_id}/ratings", tags=["Ratings"])

@router.post("/", response_model=StoreRatingOut)
def create_rating(
    store_id: int,
    rating_in: StoreRatingCreate,
    user_id: int = Query(..., description="ID do usuário que está avaliando"),
    db: GetDBDep = Depends(),
):
    rating = StoreRating(
        store_id=store_id,
        customer_id=user_id,
        rating=rating_in.rating,
        comment=rating_in.comment,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@router.get("/", response_model=List[StoreRatingOut])
def list_ratings(
    store_id: int,
    db: GetDBDep,
    skip: int = 0,
    limit: int = Query(10, le=50),
):
    ratings = (
        db.query(StoreRating)
        .filter(StoreRating.store_id == store_id)
        .order_by(StoreRating.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return ratings


@router.get("/summary")
def rating_summary(store_id: int, db: GetDBDep):
    avg = (
        db.query(func.avg(StoreRating.rating))
        .filter(StoreRating.store_id == store_id)
        .scalar()
    )
    count = (
        db.query(func.count(StoreRating.id))
        .filter(StoreRating.store_id == store_id)
        .scalar()
    )
    return {"average_rating": round(avg or 0, 1), "total_ratings": count}


@router.get("/distribution")
def rating_distribution(store_id: int, db: GetDBDep):
    distribution = (
        db.query(
            StoreRating.rating,
            func.count(StoreRating.id),
        )
        .filter(StoreRating.store_id == store_id)
        .group_by(StoreRating.rating)
        .order_by(StoreRating.rating.desc())
        .all()
    )
    dist_dict = {rating: count for rating, count in distribution}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}
    return full_dist
