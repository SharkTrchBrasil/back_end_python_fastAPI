# Em seu arquivo de serviços/emissores do app

from sqlalchemy.orm import selectinload
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.store_details import StoreDetails
from src.api.shared_schemas.store_theme import StoreThemeOut
from src.api.app.services.rating import get_product_ratings_summary


async def emit_store_updated(db, store_id: int):
    """
    Emite uma atualização com os detalhes GERAIS da loja.
    Esta função NÃO emite o catálogo de produtos.
    """
    store = db.query(models.Store).options(
        selectinload(models.Store.payment_methods),
        selectinload(models.Store.hours)
        # Carregue apenas o que for relevante para a página inicial da loja
    ).filter(models.Store.id == store_id).first()

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
    Função ÚNICA e OTIMIZADA para buscar e emitir a lista de produtos
    e TODOS os seus complementos para o cardápio do cliente.
    """
    # ✅ CONSULTA CORRIGIDA E COMPLETA
    products = db.query(models.Product).options(
        selectinload(models.Product.variant_links)      # Product -> ProductVariantLink (A Regra)
        .selectinload(models.ProductVariantLink.variant) # -> Variant (O Template)
        .selectinload(models.Variant.options)            # -> VariantOption (O Item)
        .selectinload(models.VariantOption.linked_product) # -> Product (Cross-sell)
    ).filter(
        models.Product.store_id == store_id,
        models.Product.available == True
    ).all()

    # Pega avaliações dos produtos (lógica mantida)
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products
    }

    products_data = []
    for product in products:
        # ✅ Validação com o novo schema ProductOut
        product_schema = ProductOut.model_validate(product)
        product_dict = product_schema.model_dump(mode='json')
        product_dict["rating"] = product_ratings.get(product.id)
        products_data.append(product_dict)

    # Emite a lista de produtos completa para a sala da loja
    await sio.emit('products_updated', products_data, to=f'store_{store_id}')








