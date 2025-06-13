from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import joinedload


from src import templates

from src.core import models
from src.core.database import GetDBDep

from fastapi.responses import HTMLResponse




router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/{subdomain}/{product_id}", response_class=HTMLResponse)
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

    return templates.TemplateResponse(
        "product_meta.html",
        {
            "request": request,
            "product_name": product.name,
            "product_description": product.description,

            "store_name": store.name,
            "full_url": str(request.url),
        }
    )

