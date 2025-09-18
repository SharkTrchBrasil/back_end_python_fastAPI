
from src.core import models
from src.api.schemas.products.variant import VariantCreate, VariantUpdate

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




def update_variant(db, variant_obj: models.Variant, variant_data: VariantUpdate):
    # 1. Atualiza os campos simples do Variant (name, type, etc.)
    # ✅ CORREÇÃO 3: Adicionado "linked_products_rules" à exclusão
    variant_dict = variant_data.model_dump(
        exclude_unset=True,
        exclude={"options", "linked_products_rules"}
    )
    for key, value in variant_dict.items():
        setattr(variant_obj, key, value)

    # 2. Sincroniza as opções (a parte mais importante)
    if variant_data.options is not None:
        existing_options_map = {opt.id: opt for opt in variant_obj.options}
        incoming_option_ids = {opt.id for opt in variant_data.options if opt.id is not None}

        # Exclui opções que não vieram na requisição
        for option_id, option_to_delete in existing_options_map.items():
            if option_id not in incoming_option_ids:
                db.delete(option_to_delete)

        # Atualiza ou Adiciona opções
        for option_data in variant_data.options:
            if option_data.id is not None and option_data.id in existing_options_map:
                # Atualiza uma opção existente
                update_data = option_data.model_dump(exclude_unset=True)
                existing_option = existing_options_map[option_data.id]
                for key, value in update_data.items():
                    setattr(existing_option, key, value)
            else:
                # Adiciona uma nova opção
                new_option_data = option_data.model_dump(exclude={"id"})
                new_option = models.VariantOption(
                    **new_option_data,
                    # ✅ CORREÇÃO 1: Adicionado store_id para consistência
                    # (remova se o seu modelo não tiver este campo)
                    store_id=variant_obj.store_id
                )
                variant_obj.options.append(new_option)

    # 3. Sincroniza as regras dos produtos vinculados
    # ✅ REFINAMENTO 2: Lógica mais segura e idiomática com o ORM
    if variant_data.linked_products_rules is not None:
        for rule_data in variant_data.linked_products_rules:
            # Busca o objeto do vínculo específico
            link_obj = db.query(models.ProductVariantLink).filter(
                models.ProductVariantLink.variant_id == variant_obj.id,
                models.ProductVariantLink.product_id == rule_data.product_id
            ).first()

            # Se o vínculo existir, atualiza seus atributos
            if link_obj:
                link_obj.min_selected_options = rule_data.min_selected_options
                link_obj.max_selected_options = rule_data.max_selected_options
                link_obj.available = rule_data.available
                db.add(link_obj) # Adiciona o objeto modificado à sessão

    db.commit()
    db.refresh(variant_obj)
    return variant_obj