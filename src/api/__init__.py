
from src.api.shared_schemas.product_variant_link import ProductVariantLink
from src.api.shared_schemas.variant import Variant
from src.api.shared_schemas.variant_option import VariantOption


Variant.model_rebuild()
ProductVariantLink.model_rebuild()
VariantOption.model_rebuild() # Adicionado por segurança, embora possa não ser estritamente necessário
