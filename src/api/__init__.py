
from src.api.schemas.product_variant_link import ProductVariantLink
from src.api.schemas.variant import Variant
from src.api.schemas.variant_option import VariantOption


Variant.model_rebuild()
ProductVariantLink.model_rebuild()
VariantOption.model_rebuild() # Adicionado por segurança, embora possa não ser estritamente necessário
