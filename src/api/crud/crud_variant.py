
from src.core import models
from src.api.schemas.products.variant import VariantCreate

def create_variant(db, *, store_id: int, variant_data: VariantCreate) -> models.Variant:
    """
    Cria um novo grupo de complementos (Variant) e suas opções aninhadas.
    """
    # 1. Cria um dicionário com os dados do Variant, excluindo as opções por enquanto.
    variant_dict = variant_data.model_dump(exclude={'options'})

    # 2. Cria a instância do objeto SQLAlchemy para o Variant principal.
    db_variant = models.Variant(**variant_dict, store_id=store_id)

    # 3. ✅ A LÓGICA CORRETA PARA AS OPÇÕES
    # Itera sobre os dados das opções que vieram do Pydantic...
    if variant_data.options:
        for option_pydantic in variant_data.options:
            # ...e para cada uma, cria um OBJETO do modelo SQLAlchemy 'VariantOption'.
            db_option = models.VariantOption(**option_pydantic.model_dump())
            # Adiciona o objeto criado (a "peça de LEGO") à lista de opções do Variant.
            db_variant.options.append(db_option)

    # 4. Adiciona tudo à sessão e salva no banco.
    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)

    return db_variant