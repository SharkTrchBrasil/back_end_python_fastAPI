from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import Dict, Any

from src.core.models import StoreRating, ProductRating


def get_store_ratings_summary(db: Session, *, store_id: int) -> dict:
    """
    Busca um resumo completo e otimizado das avaliações de uma loja.
    Faz apenas UMA query no banco de dados.
    """
    # ✅ 1. Busca todas as avaliações e seus clientes de uma só vez.
    ratings_list = db.query(StoreRating).options(
        joinedload(StoreRating.customer)
    ).filter(StoreRating.store_id == store_id).order_by(StoreRating.created_at.desc()).all()

    if not ratings_list:
        return {
            "average_rating": 0.0, "total_ratings": 0,
            "distribution": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}, "ratings": []
        }

    # ✅ 2. Calcula tudo em memória (muito mais rápido).
    total_ratings = len(ratings_list)
    total_stars = sum(r.stars for r in ratings_list)
    average_rating = round(total_stars / total_ratings, 1) if total_ratings > 0 else 0.0

    distribution = {i: 0 for i in range(5, 0, -1)}
    for r in ratings_list:
        distribution[r.stars] += 1

    # ✅ 3. Monta a resposta final.
    return {
        "average_rating": float(average_rating),
        "total_ratings": total_ratings,
        "distribution": distribution,
        "ratings": [
            {
                "id": r.id,
                "customer_name": r.customer.name if r.customer else "Anônimo",
                "stars": r.stars,
                "is_active": r.is_active,
                "comment": r.comment,
                "owner_reply": r.owner_reply,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in ratings_list
        ],
    }


def get_product_ratings_summary(db: Session, *, product_id: int) -> dict:
    """
    Busca um resumo completo e otimizado das avaliações de um produto.
    Faz apenas UMA query no banco de dados.
    """
    # ✅ 1. Busca todas as avaliações e seus clientes de uma só vez.
    ratings_list = db.query(ProductRating).options(
        joinedload(ProductRating.customer)
    ).filter(ProductRating.product_id == product_id).order_by(ProductRating.created_at.desc()).all()

    if not ratings_list:
        return {
            "average_rating": 0.0, "total_ratings": 0,
            "distribution": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}, "ratings": []
        }

    # ✅ 2. Calcula tudo em memória.
    total_ratings = len(ratings_list)
    total_stars = sum(r.stars for r in ratings_list)
    average_rating = round(total_stars / total_ratings, 1) if total_ratings > 0 else 0.0

    distribution = {i: 0 for i in range(5, 0, -1)}
    for r in ratings_list:
        distribution[r.stars] += 1

    # ✅ 3. Monta a resposta final.
    return {
        "average_rating": float(average_rating),
        "total_ratings": total_ratings,
        "distribution": distribution,
        "ratings": [
            {
                "id": r.id,
                "customer_name": r.customer.name if r.customer else "Anônimo",
                "stars": r.stars,
                "is_active": r.is_active,
                "comment": r.comment,
                "owner_reply": r.owner_reply,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in ratings_list
        ],
    }





def get_all_ratings_summaries_for_store(db, store_id: int) -> dict[int, RatingsSummaryOut]:
    """
    Busca o resumo das avaliações para TODOS os produtos de uma loja
    em uma única e eficiente query.
    """
    # Agrupa por product_id, calcula a média de 'stars' e a contagem de 'id'
    results = db.query(
        models.ProductRating.product_id,
        func.avg(models.ProductRating.stars).label('average_rating'),
        func.count(models.ProductRating.id).label('rating_count')
    ).join(models.Product) \
     .filter(models.Product.store_id == store_id) \
     .group_by(models.ProductRating.product_id) \
     .all()

    # Transforma o resultado em um dicionário para acesso rápido:
    # {product_id: RatingsSummaryOut, ...}
    return {
        product_id: RatingsSummaryOut(
            average_rating=float(avg) if avg is not None else 0.0,
            rating_count=count
        )
        for product_id, avg, count in results
    }