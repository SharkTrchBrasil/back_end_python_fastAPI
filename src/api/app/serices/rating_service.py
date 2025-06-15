from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from src.core import models


def get_store_ratings_summary(db: Session, store_id: int) -> Dict[str, Any]:
    avg = db.query(func.avg(models.StoreRating.rating)).filter(models.StoreRating.store_id == store_id).scalar() or 0
    count = db.query(func.count(models.StoreRating.id)).filter(models.StoreRating.store_id == store_id).scalar() or 0
    distribution = (
        db.query(models.StoreRating.rating, func.count(models.StoreRating.id))
        .filter(models.StoreRating.store_id == store_id)
        .group_by(models.StoreRating.rating)
        .order_by(models.StoreRating.rating.desc())
        .all()
    )
    dist_dict = {rating: count for rating, count in distribution}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}

    ratings_list = db.query(models.StoreRating).filter(models.StoreRating.store_id == store_id).order_by(models.StoreRating.created_at.desc()).all()

    return {
        "average_rating": round(avg, 1),
        "total_ratings": count,
        "distribution": full_dist,
        "ratings": [rating_to_dict(r) for r in ratings_list]
    }


def get_product_ratings_summary(db: Session, product_id: int) -> Dict[str, Any]:
    avg = db.query(func.avg(models.ProductRating.rating)).filter(models.ProductRating.product_id == product_id).scalar() or 0
    count = db.query(func.count(models.ProductRating.id)).filter(models.ProductRating.product_id == product_id).scalar() or 0
    distribution = (
        db.query(models.ProductRating.rating, func.count(models.ProductRating.id))
        .filter(models.ProductRating.product_id == product_id)
        .group_by(models.ProductRating.rating)
        .order_by(models.ProductRating.rating.desc())
        .all()
    )
    dist_dict = {rating: count for rating, count in distribution}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}

    ratings_list = db.query(models.ProductRating).filter(models.ProductRating.product_id == product_id).order_by(models.ProductRating.created_at.desc()).all()

    return {
        "average_rating": round(avg, 1),
        "total_ratings": count,
        "distribution": full_dist,
        "ratings": [rating_to_dict(r) for r in ratings_list]
    }


def rating_to_dict(rating) -> dict:
    return {
        "id": rating.id,
        "customer_name": rating.customer.name if rating.customer else None,
        "rating": rating.rating,
        "comment": rating.comment,
        "created_at": rating.created_at.isoformat() if rating.created_at else None,
    }
