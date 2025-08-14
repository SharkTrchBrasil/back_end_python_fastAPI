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


async def emit_products_updated(db, store_id: int):
    """
    Emite uma atualização da lista de produtos, garantindo que todos os
    relacionamentos necessários, incluindo as opções padrão, sejam carregados.
    """
    # ✅ CONSULTA ATUALIZADA PARA INCLUIR default_options
    products = db.query(models.Product).options(
        selectinload(models.Product.category),  # Carrega a categoria
        selectinload(models.Product.default_options),  # Carrega as opções padrão
        selectinload(models.Product.variant_links)
        .selectinload(models.ProductVariantLink.variant)
        .selectinload(models.Variant.options)
        .selectinload(models.VariantOption.linked_product)
    ).filter(
        models.Product.store_id == store_id,
    ).all()

    # A função _prepare_products_payload agora recebe a lista já carregada corretamente
    products_data = _prepare_products_payload(db, products)

    await sio.emit('products_updated', products_data, to=f'store_{store_id}')


def _prepare_products_payload(db, products: list[models.Product]) -> list[dict]:
    """
    Prepara o payload de produtos com seus ratings.
    Esta função agora confia que a lista 'products' já vem com todos os
    relacionamentos necessários pré-carregados (eagerly loaded).
    """
    # Pega as avaliações de todos os produtos de uma vez para otimização
    product_ratings = {p.id: get_product_ratings_summary(db, product_id=p.id) for p in products}

    products_payload = []
    for p in products:
        # Valida o objeto SQLAlchemy 'p' (que já tem default_options) com o schema ProductOut.
        # O @computed_field 'default_option_ids' será executado aqui.
        product_schema = ProductOut.model_validate(p)
        product_dict = product_schema.model_dump(mode='json')
        product_dict["rating"] = product_ratings.get(p.id)
        products_payload.append(product_dict)

    return products_payload