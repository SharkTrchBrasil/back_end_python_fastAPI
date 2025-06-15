from typing import List

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from src import templates
from src.api.shared_schemas.product import ProductOut, ProductRatingOut, ProductRatingCreate
from src.core import models
from src.core.database import GetDBDep
from src.core.models import ProductRating

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/{subdomain}/{product_id}")
def get_product_by_subdomain(
    request: Request,
    subdomain: str,
    product_id: int,
    db: GetDBDep,
):
    # Busca loja autorizada pelo subdomínio
    totem_auth = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.store_url == subdomain,
        models.TotemAuthorization.granted == True
    ).first()

    if not totem_auth:
        raise HTTPException(status_code=404, detail=f"Loja '{subdomain}' não encontrada ou não autorizada")

    store = totem_auth.store

    product = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter(
        models.Product.id == product_id,
        models.Product.store_id == store.id,
        models.Product.available == True
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou indisponível")

    # VERIFICA O TIPO DE RESPOSTA ESPERADA
    accept = request.headers.get("accept", "")

    if "application/json" in accept:
        # Resposta para app Flutter
        return ProductOut.from_orm(product)

    # Resposta HTML para redes sociais
    return templates.TemplateResponse(
        "product_meta.html",
        {
            "request": request,
            "product_name": product.name,
            "product_description": product.description,
            "product_image": "",  # Aqui você pode colocar a imagem com get_presigned_url(product.file_key)
            "store_name": store.name,
            "full_url": str(request.url),
        }
    )







@router.post("/{product_id}/ratings", response_model=ProductRatingOut)
def create_product_rating(
    product_id: int,
    db: GetDBDep,
    rating_in: ProductRatingCreate,
    user_id: int = Query(..., description="ID do usuário que está avaliando"),

):
    rating = ProductRating(
        product_id=product_id,
        customer_id=user_id,
        rating=rating_in.rating,
        comment=rating_in.comment,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@router.get("/", response_model=List[ProductRatingOut])
def list_product_ratings(
    product_id: int,
    db: GetDBDep,
    skip: int = 0,
    limit: int = Query(10, le=50),
):
    ratings = (
        db.query(ProductRating)
        .filter(ProductRating.product_id == product_id)
        .order_by(ProductRating.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return ratings


@router.get("/summary")
def product_rating_summary(product_id: int, db: GetDBDep):
    avg = (
        db.query(func.avg(ProductRating.rating))
        .filter(ProductRating.product_id == product_id)
        .scalar()
    )
    count = (
        db.query(func.count(ProductRating.id))
        .filter(ProductRating.product_id == product_id)
        .scalar()
    )
    return {"average_rating": round(avg or 0, 1), "total_ratings": count}


@router.get("/distribution")
def product_rating_distribution(product_id: int, db: GetDBDep):
    distribution = (
        db.query(
            ProductRating.rating,
            func.count(ProductRating.id),
        )
        .filter(ProductRating.product_id == product_id)
        .group_by(ProductRating.rating)
        .order_by(ProductRating.rating.desc())
        .all()
    )
    dist_dict = {rating: count for rating, count in distribution}
    full_dist = {i: dist_dict.get(i, 0) for i in range(5, 0, -1)}
    return full_dist
