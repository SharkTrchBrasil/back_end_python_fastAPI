# Em seu arquivo de serviços/emissores do app

from sqlalchemy.orm import selectinload

from src.api.admin.services.subscription_service import SubscriptionService
from src.api.crud import store_crud
from src.api.schemas.products.category import Category
from src.core import models

from src.core.utils.enums import ProductStatus
from src.socketio_instance import sio
from src.api.schemas.products.product import ProductOut, logger
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_theme import StoreThemeOut
from src.api.app.services.rating import get_store_ratings_summary




async def emit_store_updated(db, store_id: int):
    """
    ✅ VERSÃO CORRIGIDA - USA O MESMO MÉTODO DO ADMIN

    Emite detalhes atualizados da loja para o namespace /totem (público)
    """
    try:
        # ✅ 1. BUSCA A LOJA DO BANCO
        store_model = store_crud.get_store_base_details(db=db, store_id=store_id)

        if not store_model:
            logger.warning(f"⚠️ Loja {store_id} não encontrada")
            return

        # ✅ 2. USA O MESMO MÉTODO QUE O ADMIN USA
        # Isso garante que os campos computados sejam adicionados
        store_dict = SubscriptionService.get_store_dict_with_subscription(
            store=store_model,
            db=db
        )

        # ✅ 3. VALIDA COM PYDANTIC (AGORA VAI FUNCIONAR)
        store_schema = StoreDetails.model_validate(store_dict)

        # ✅ 4. EMITE PARA O TOTEM
        await sio.emit(
            'store_details_updated',
            {"store": store_schema.model_dump(mode='json', by_alias=True)},
            namespace='/',  # ← Namespace do totem (público)
            room=f"store_{store_id}"
        )

        logger.info(f"✅ [TOTEM] store_details_updated emitido para loja {store_id}")

    except Exception as e:
        logger.error(f'❌ Erro ao emitir store_details_updated (TOTEM): {e}', exc_info=True)



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

    ).filter(
        # ✅ 2. ADICIONE ESTE FILTRO PARA ESCONDER OS ARQUIVADOS
        models.Product.status != ProductStatus.ARCHIVED
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