# Em seu arquivo de serviços/emissores do app

from sqlalchemy.orm import selectinload

from src.api.crud import store_crud
from src.core import models
from src.socketio_instance import sio
from src.api.schemas.products.product import ProductOut
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_theme import StoreThemeOut
from src.api.app.services.rating import get_store_ratings_summary


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


# Em algum lugar, garanta que a função otimizada de ratings esteja disponível
# from src.api.admin.logic.rating_logic import get_all_ratings_summaries_for_store

# ✅ FUNÇÃO ATUALIZADA E OTIMIZADA PARA O TOTEM
async def emit_products_updated(db, store_id: int):
    """
    Busca a lista de produtos COMPLETA, alinhada com a nova arquitetura,
    e emite para todos os clientes da loja.
    """
    print(f"📢 [TOTEM] Preparando emissão 'products_updated' para a loja {store_id}...")

    # ✅ 1. CONSULTA CORRIGIDA E COMPLETA
    #    Agora carrega `category_links` em vez de `category`.
    products_from_db = db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
        .selectinload(models.ProductVariantLink.variant)
        .selectinload(models.Variant.options)
        .selectinload(models.VariantOption.linked_product)
    ).filter(
        models.Product.store_id == store_id,
        models.Product.available == True  # ✅ Importante: O totem só precisa ver produtos ativos
    ).order_by(models.Product.priority).all()

    # ✅ 2. ANEXA AS AVALIAÇÕES DE FORMA OTIMIZADA
    #    Uma única chamada ao banco para todas as avaliações da loja.

    all_ratings = get_store_ratings_summary(db, store_id=store_id)

    #    Distribui os resultados em memória (muito mais rápido).
    for product in products_from_db:
        product.rating = all_ratings.get(product.id)

    # 3. Serializa a lista de produtos usando o schema ProductOut.
    products_payload = [ProductOut.model_validate(p).model_dump(mode='json') for p in products_from_db]

    # 4. Emite o payload final para a sala correta do totem/cardápio.
    room_name = f'store_{store_id}'
    await sio.emit('products_updated', products_payload, to=room_name)
    print(f"✅ [TOTEM] Emissão 'products_updated' para a sala: {room_name} concluída.")