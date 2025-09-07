# Em seu arquivo de serviços/emissores do app

from sqlalchemy.orm import selectinload

from src.api.crud import store_crud
from src.core import models
from src.core.models import Category
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



async def emit_products_updated(db, store_id: int):
    """
    Busca TODOS os dados do cardápio (produtos E categorias) e emite para os clientes.
    Esta é a fonte da verdade para o frontend.
    """
    print(f"📢 Preparando emissão completa de cardápio para a loja {store_id}...")

    # --- 1. BUSCA DE PRODUTOS (COM RELACIONAMENTOS CORRIGIDOS) ---
    products_from_db = db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
        .selectinload(models.ProductVariantLink.variant)
        .selectinload(models.Variant.options)
        .selectinload(models.VariantOption.linked_product),
        selectinload(models.Product.prices).selectinload(models.FlavorPrice.size_option),  # ✅ Adicionado
      #  selectinload(models.Product.tags)  # ✅ Adicionado (se 'tags' for uma relação)
    ).filter(
        models.Product.store_id == store_id,
        models.Product.available == True
    ).order_by(models.Product.priority).all()

    # --- 2. BUSCA DAS AVALIAÇÕES (SUA OTIMIZAÇÃO, ESTÁ PERFEITA) ---
    all_ratings = get_store_ratings_summary(db, store_id=store_id)
    for product in products_from_db:
        product.rating = all_ratings.get(product.id)

    # --- 3. ✨ BUSCA DE CATEGORIAS (A GRANDE ADIÇÃO) ---
    #    Buscamos TODAS as categorias e sua estrutura interna completa.
    categories_from_db = db.query(models.Category).options(
        selectinload(models.Category.option_groups).selectinload(models.OptionGroup.items),
        selectinload(models.Category.schedules).selectinload(models.CategorySchedule.time_shifts),
        selectinload(models.Category.product_links)  # Opcional, mas bom ter
    ).filter(
        models.Category.store_id == store_id,
        models.Category.is_active == True
    ).order_by(models.Category.priority).all()

    # --- 4. SERIALIZAÇÃO E MONTAGEM DO PAYLOAD FINAL ---
    products_payload = [ProductOut.model_validate(p).model_dump(mode='json') for p in products_from_db]
    categories_payload = [Category.model_validate(c).model_dump(mode='json') for c in categories_from_db]

    final_payload = {
        "products": products_payload,
        "categories": categories_payload
    }

    # --- 5. EMISSÃO PARA O SOCKET ---
    room_name = f'store_{store_id}'
    await sio.emit('products_updated', final_payload, to=room_name)
    print(f"✅ Emissão 'products_updated' para a sala: {room_name} concluída.")