from fastapi import APIRouter, HTTPException
from src.api import crud
from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.crud import crud_product
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

# ✅ 1. NOVO ROTEADOR DEDICADO
#    Note que ele não tem prefixo. O prefixo será dado por quem o incluir.
router = APIRouter(tags=["Product-Category Links"])

# ✅ 2. A SUA ROTA DE DELETE AGORA VIVE AQUI
@router.delete(
    "/{category_id}", # O path agora é relativo ao produto
    status_code=204,
    summary="Remove a product from a specific category"
)
async def remove_product_from_category_route(
    product_id: int, # Vem do prefixo do roteador pai
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