

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import joinedload

from src.api.shared_schemas.product import ProductOut
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetPublicProductDep

from fastapi import APIRouter, HTTPException
from src.core.database import GetDBDep
from src.core import models
from src.api.shared_schemas.product import ProductOut

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/{subdomain}/{product_id}", response_model=ProductOut)
def get_product_by_subdomain(
    subdomain: str,
    product_id: int,
    db: GetDBDep,
):
    # Busca loja autorizada pelo subdomínio
    totem_auth = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.store_url == subdomain,
        models.TotemAuthorization.granted == True  # Só lojas autorizadas
    ).first()

    if not totem_auth:
        raise HTTPException(status_code=404, detail=f"Loja '{subdomain}' não encontrada ou não autorizada")


    product = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter(
        models.Product.id == product_id,
        models.Product.store_id == totem_auth.store.id,
        models.Product.available == True
    ).first()



    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou indisponível")

    return product
