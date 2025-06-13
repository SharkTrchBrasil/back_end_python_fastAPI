from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import joinedload
from fastapi.responses import JSONResponse, HTMLResponse
from src.api.shared_schemas.product import ProductOut
from src.core import models
from src.core.database import GetDBDep
from src import templates


router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/{subdomain}/{product_id}", response_class=HTMLResponse)
def get_product_by_subdomain(
    request: Request,
    subdomain: str,
    product_id: int,
    db: GetDBDep,
):
    # Verifica loja autorizada pelo subdomínio
    totem_auth = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.store_url == subdomain,
        models.TotemAuthorization.granted == True
    ).first()

    if not totem_auth:
        raise HTTPException(status_code=404, detail=f"Loja '{subdomain}' não encontrada ou não autorizada")

    store = totem_auth.store

    # Busca o produto com joins
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

    # Verifica se o client quer JSON
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header:
        return product




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
