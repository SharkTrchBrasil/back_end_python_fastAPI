from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import selectinload # Use selectinload para coleções

from src import templates
from src.core import models
from src.core.database import GetDBDep


# USE IMPORTAÇÃO DIRETA:
from src.api.schemas.product.product import ProductOut
router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/{subdomain}/{product_id}")
def get_product_by_subdomain(
    request: Request,
    subdomain: str,
    product_id: int,
    db: GetDBDep,
):
    # Busca da loja (seu código original está correto)
    totem_auth = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.store_url == subdomain,
        models.TotemAuthorization.granted == True
    ).first()

    if not totem_auth:
        raise HTTPException(status_code=404, detail=f"Loja '{subdomain}' não encontrada ou não autorizada")

    store = totem_auth.store

    # ✅ CONSULTA CORRIGIDA E COMPLETA
    product = db.query(models.Product).options(
        selectinload(models.Product.variant_links)      # Product -> ProductVariantLink (A Regra)
        .selectinload(models.ProductVariantLink.variant) # -> Variant (O Template)
        .selectinload(models.Variant.options)            # -> VariantOption (O Item)
        .selectinload(models.VariantOption.linked_product) # -> Product (Cross-sell)
    ).filter(
        models.Product.id == product_id,
        models.Product.store_id == store.id,
        #models.Product.available == True
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou indisponível")

    accept = request.headers.get("accept", "")

    if "application/json" in accept:
        # ✅ CHAMADA Pydantic ATUALIZADA
        return ProductOut.model_validate(product)

    # Resposta HTML para redes sociais (seu código original está correto)
    return templates.TemplateResponse(
        "product_meta.html",
        {
            "request": request,
            "product_name": product.name,
            "product_description": product.description,
            "product_image": product.image_path, # Usando o computed_field do schema
            "store_name": store.name,
            "full_url": str(request.url),
        }
    )