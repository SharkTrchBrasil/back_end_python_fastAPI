def rebuild_all_models():
    from .product.product import ProductOut, ProductWizardCreate
    from .variant.variant import Variant
    from .variant.variant_option import VariantOption
    from .product.product_variant_link import ProductVariantLink

    ProductOut.model_rebuild()
    ProductWizardCreate.model_rebuild()
    Variant.model_rebuild()
    VariantOption.model_rebuild()
    ProductVariantLink.model_rebuild()