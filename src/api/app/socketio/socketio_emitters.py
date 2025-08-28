# Em seu arquivo de serviços/emissores do app

from sqlalchemy.orm import selectinload, joinedload

from src.api.crud import store_crud
from src.core import models
from src.socketio_instance import sio
from src.api.schemas.product import ProductOut
from src.api.schemas.store_details import StoreDetails
from src.api.schemas.store_theme import StoreThemeOut
from src.api.app.services.rating import get_product_ratings_summary


async def emit_store_updated(db, store_id: int):
    """
    Emite uma atualização com os detalhes GERAIS da loja.
    Esta função NÃO emite o catálogo de produtos.
    """

    store = store_crud.get_store_for_customer_view(db=db, store_id=store_id)

    if store:
        await sio.emit(
            'store_updated',
            StoreDetails.model_validate(store).model_dump(mode='json'),
            to=f'store_{store.id}'
        )

async def emit_theme_updated(theme: models.StoreTheme):
    """ Emite uma atualização do tema da loja. (Sua função original está correta) """
    pydantic_theme = StoreThemeOut.model_validate(theme).model_dump(mode='json')
    await sio.emit(
        'theme_updated',
        pydantic_theme,
        to=f'store_{theme.store_id}'
    )



# ✅ FUNÇÃO ATUALIZADA E CORRIGIDA
async def emit_products_updated(db, store_id: int):
    """
    Busca a lista de produtos ATUALIZADA com seus VÍNCULOS de categoria
    e emite para todos os clientes da loja.
    """
    print(f"📢 Preparando emissão 'products_updated' para a loja {store_id}...")

    # 1. CONSULTA CORRIGIDA para usar a nova estrutura de muitos-para-muitos
    products_from_db = db.query(models.Product).options(
        # ✅ CORREÇÃO: Carrega os links da categoria e, dentro de cada link, a categoria em si.
        selectinload(models.Product.category_links)
        .selectinload(models.ProductCategoryLink.category),

        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
        .selectinload(models.ProductVariantLink.variant)
        .selectinload(models.Variant.options)
        .selectinload(models.VariantOption.linked_product)
    ).filter(models.Product.store_id == store_id).all()

    # 2. Anexa as avaliações (lógica inalterada)
    product_ratings = {
        p.id: get_product_ratings_summary(db, product_id=p.id)
        for p in products_from_db
    }
    for product in products_from_db:
        product.rating = product_ratings.get(product.id)

    # 3. Serializa a lista de produtos (lógica inalterada, o Pydantic já sabe lidar com `category_links`)
    products_payload = [ProductOut.model_validate(p).model_dump(mode='json') for p in products_from_db]

    # 4. Emite o payload final (lógica inalterada)
    await sio.emit('products_updated', products_payload, to=f'store_{store_id}')
    print(f"✅ Emissão 'products_updated' para a loja {store_id} concluída.")