from fastapi import HTTPException

from src.core import models


def validate_order_variants(db, product_data):
    product_id = product_data["product_id"]

    # 1. Verifica se as variantes estão ligadas ao produto
    valid_variant_ids = db.query(models.ProductVariantProduct.variant_id).filter_by(
        product_id=product_id
    ).all()
    valid_variant_ids = [v[0] for v in valid_variant_ids]

    for variant_data in product_data.get("variants", []):
        variant_id = variant_data["variant_id"]

        if variant_id not in valid_variant_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Variante inválida (id={variant_id}) no produto ID {product_id}"
            )

        # 2. Verifica se as opções pertencem à variante
        valid_option_ids = db.query(models.VariantOptions.id).filter_by(
            variant_id=variant_id
        ).all()
        valid_option_ids = [o[0] for o in valid_option_ids]

        for option_data in variant_data.get("options", []):
            option_id = option_data["variant_option_id"]
            if option_id not in valid_option_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Opção inválida (id={option_id}) em variante ID {variant_id} no produto ID {product_id}"
                )
