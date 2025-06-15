from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.core import models


def get_ratings_summary(db: Session, *, store_id: int | None = None, product_id: int | None = None) -> Dict[str, Any]:
    query = db.query(models.Rating)

    if store_id is not None:
        query = query.filter(models.Rating.store_id == store_id)
    elif product_id is not None:
        query = query.filter(models.Rating.product_id == product_id)
    else:
        raise ValueError("Você deve informar store_id ou product_id.")

    avg = query.with_entities(func.avg(models.Rating.stars)).scalar() or 0
    count = query.with_entities(func.count(models.Rating.id)).scalar() or 0

    distribution_query = (
        query.with_entities(models.Rating.stars, func.count(models.Rating.id))
        .group_by(models.Rating.stars)
        .order_by(models.Rating.stars.desc())
        .all()
    )
    dist_dict = {stars: cnt for stars, cnt in distribution_query}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}

    ratings_list = query.order_by(models.Rating.created_at.desc()).all()

    return {
        "average_rating": round(avg, 1),
        "total_ratings": count,
        "distribution": full_dist,
        "ratings": [
            {
                "id": r.id,
                "customer_name": r.customer.name if r.customer else None,
                "stars": r.stars,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in ratings_list
        ],
    }
