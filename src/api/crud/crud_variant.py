
from src.core import models
from src.api.schemas.products.variant import VariantCreate

from src.core import models
from src.api.schemas.products.variant import VariantCreate

def create_variant(db, *, store_id: int, variant_data: VariantCreate) -> models.Variant:
    """
    Cria um novo grupo de complementos (Variant) e suas opções aninhadas.
    """
    variant_dict = variant_data.model_dump(exclude={'options'})
    db_variant = models.Variant(**variant_dict, store_id=store_id)

    if variant_data.options:
        for option_pydantic in variant_data.options:
            # ✅ CORREÇÃO APLICADA AQUI:
            # Além dos dados do Pydantic, adicionamos explicitamente o store_id.
            db_option = models.VariantOption(
                **option_pydantic.model_dump(),
                store_id=store_id
            )
            db_variant.options.append(db_option)

    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)

    return db_variant