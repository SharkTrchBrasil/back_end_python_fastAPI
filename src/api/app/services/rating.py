from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.core.models import StoreRating, ProductRating

def get_store_ratings_summary(db: Session, *, store_id: int) -> dict:
    from src.core.models import StoreRating

    query = db.query(StoreRating).filter(StoreRating.store_id == store_id)

    avg = query.with_entities(func.avg(StoreRating.stars)).scalar() or 0
    count = query.with_entities(func.count(StoreRating.id)).scalar() or 0

    distribution_query = (
        query.with_entities(StoreRating.stars, func.count(StoreRating.id))
        .group_by(StoreRating.stars)
        .order_by(StoreRating.stars.desc())
        .all()
    )
    dist_dict = {stars: cnt for stars, cnt in distribution_query}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}

    ratings_list = query.order_by(StoreRating.created_at.desc()).all()

    return {
        "average_rating": float(round(avg, 1)),
        "total_ratings": count,
        "distribution": full_dist,
        "ratings": [
            {
                "id": r.id,
                "customer_name": r.customer.name if r.customer else None,
                "stars": r.stars,
                "comment": r.comment,
                "owner_reply": r.owner_reply,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in ratings_list
        ],
    }






def get_product_ratings_summary(db: Session, *, product_id: int) -> dict:
    from src.core.models import ProductRating

    query = db.query(ProductRating).filter(ProductRating.product_id == product_id)

    avg = query.with_entities(func.avg(ProductRating.stars)).scalar() or 0
    count = query.with_entities(func.count(ProductRating.id)).scalar() or 0

    distribution_query = (
        query.with_entities(ProductRating.stars, func.count(ProductRating.id))
        .group_by(ProductRating.stars)
        .order_by(ProductRating.stars.desc())
        .all()
    )
    dist_dict = {stars: cnt for stars, cnt in distribution_query}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}

    ratings_list = query.order_by(ProductRating.created_at.desc()).all()

    return {
        "average_rating": float(round(avg, 1)),
        "total_ratings": count,
        "distribution": full_dist,
        "ratings": [
            {
                "id": r.id,
                "customer_name": r.customer.name if r.customer else None,
                "stars": r.stars,
                "comment": r.comment,
                "owner_reply": r.owner_reply,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in ratings_list
        ],
    }















