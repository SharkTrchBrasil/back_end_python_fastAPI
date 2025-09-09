from fastapi import APIRouter, HTTPException
from src.api import crud
from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.crud import crud_product
from src.api.schemas.products.product_category_link import ProductCategoryLinkOut, ProductCategoryLinkUpdate
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Product-Category Links"])


@router.delete(
    "/{category_id}",
    status_code=204,
    summary="Remove a product from a specific category"
)
async def remove_product_from_category_route(
    product_id: int,
    category_id: int,
    store: GetStoreDep,
    db: GetDBDep,
):
    """
    Desvincula um produto de uma categoria sem apagar o produto do sistema.
    """
    rows_deleted = crud_product.remove_product_from_category(
        db=db,
        store_id=store.id,
        product_id=product_id,
        category_id=category_id
    )
    if rows_deleted == 0:
        print(f"Nenhum vínculo encontrado para o produto {product_id} na categoria {category_id}.")
    await emit_updates_products(db, store.id)
    return


# ✅ NOVA ROTA 'PATCH' PARA ATUALIZAÇÕES PARCIAIS
@router.patch("/{category_id}", response_model=ProductCategoryLinkOut)
async def update_product_category_link_route(
    product_id: int,
    category_id: int,
    payload: ProductCategoryLinkUpdate, # Usa o novo schema
    store: GetStoreDep,
    db: GetDBDep,
):
    """
    Atualiza dados de um vínculo produto-categoria (ex: pausar/ativar).
    """
    updated_link = crud_product.update_product_category_link(
        db=db,
        store_id=store.id,
        product_id=product_id,
        category_id=category_id,
        payload=payload,
    )

    if not updated_link:
        raise HTTPException(status_code=404, detail="Vínculo entre produto e categoria não encontrado.")

    await emit_updates_products(db, store.id)
    return updated_link