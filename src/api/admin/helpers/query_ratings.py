# SUGESTÃO: Coloque esta função onde você tem suas outras lógicas de "queries"

from sqlalchemy import func
from src.api.schemas.rating import RatingsSummaryOut
from src.core import models


def get_all_ratings_summaries_for_store(db, store_id: int) -> dict[int, RatingsSummaryOut]:
    """
    Busca o resumo das avaliações para TODOS os produtos de uma loja
    em uma única e eficiente query.
    """
    # Agrupa por product_id, calcula a média e a contagem
    results = db.query(
        models.ProductRating.product_id,
        func.avg(models.ProductRating.rating).label('average_rating'),
        func.count(models.ProductRating.id).label('rating_count')
    ).join(models.Product) \
     .filter(models.Product.store_id == store_id) \
     .group_by(models.ProductRating.product_id) \
     .all()

    # Transforma o resultado em um dicionário para acesso rápido: {product_id: RatingsSummaryOut}
    return {
        product_id: RatingsSummaryOut(average_rating=avg or 0, rating_count=count)
        for product_id, avg, count in results
    }