# from src.api.schemas.category import CategoryOut, CategoryBase
# from src.api.schemas.product import Product, ProductOut, ProductCreate, ProductUpdate, KitComponentOut
# from src.api.schemas.product_variant_link import ProductVariantLinkCreate, ProductVariantLinkUpdate
# from src.api.schemas.variant import Variant, VariantCreate, VariantUpdate
# from src.api.schemas.variant_option import VariantOption, VariantOptionCreate, VariantOptionUpdate
#
# # 2. Agora que todas as classes estão carregadas, chame o model_rebuild()
# # A ordem aqui não importa, contanto que todos os imports estejam acima.
# Product.model_rebuild()
# ProductOut.model_rebuild() # ✅ Adicionado
# KitComponentOut.model_rebuild() # ✅ Adicionado
# CategoryOut.model_rebuild()
# Variant.model_rebuild()
# VariantOption.model_rebuild()
# ProductVariantLink.model_rebuild()
#
# # Opcional: defina __all__ para exportar publicamente os schemas
# __all__ = [
#     "Product", "ProductOut", "ProductCreate", "ProductUpdate","KitComponentOut",
#     "CategoryBase", "CategoryOut",
#     "Variant", "VariantCreate", "VariantUpdate",
#     "VariantOption", "VariantOptionCreate", "VariantOptionUpdate",
#     "ProductVariantLink", "ProductVariantLinkCreate", "ProductVariantLinkUpdate",
# ]