# Em seu arquivo de serviços/emissores do app

from sqlalchemy.orm import selectinload
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

    store = db.query(models.Store).options(
        # ✅ CORREÇÃO: Carregando a nova estrutura de pagamentos em cascata
        selectinload(models.Store.payment_activations)  # Store -> Ativações da loja
        .selectinload(models.StorePaymentMethodActivation.platform_method)  # Ativação -> Método da Plataforma
        .selectinload(models.PlatformPaymentMethod.category)  # Método -> Categoria
        .selectinload(models.PaymentMethodCategory.group),
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


# ✅ FUNÇÃO ATUALIZADA E AUTOSSUFICIENTE
async def emit_products_updated(db, store_id: int):
    """
    Busca a lista de produtos ATUALIZADA, serializa-a incluindo as avaliações,
    e emite para todos os clientes da loja.
    """
    print(f"📢 Preparando emissão 'products_updated' para a loja {store_id}...")

    # 1. Consulta completa que carrega tudo que o ProductOut precisa
    products_from_db = db.query(models.Product).options(
        selectinload(models.Product.category),
        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
        .selectinload(models.ProductVariantLink.variant)
        .selectinload(models.Variant.options)
        .selectinload(models.VariantOption.linked_product)
    ).filter(models.Product.store_id == store_id).all()

    # 2. Anexa as avaliações aos objetos SQLAlchemy antes de serializar
    product_ratings = {
        p.id: get_product_ratings_summary(db, product_id=p.id)
        for p in products_from_db
    }
    for product in products_from_db:
        product.rating = product_ratings.get(product.id)

    # 3. Serializa a lista de produtos usando o schema ProductOut.
    #    O Pydantic irá ler o atributo 'rating' e executar os @computed_field.
    products_payload = [ProductOut.model_validate(p).model_dump(mode='json') for p in products_from_db]

    # 4. Emite o payload final
    await sio.emit('products_updated', products_payload, to=f'store_{store_id}')
    print(f"✅ Emissão 'products_updated' para a loja {store_id} concluída.")

