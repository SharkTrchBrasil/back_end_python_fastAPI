from src.api.schemas.category import CategoryOut, CategoryBase
from src.api.schemas.product import ProductOut, KitComponentOut
from src.api.schemas.product_variant_link import ProductVariantLink, ProductVariantLinkCreate, ProductVariantLinkUpdate
from src.api.schemas.variant import Variant, VariantCreate, VariantUpdate
from src.api.schemas.variant_option import VariantOption, VariantOptionCreate, VariantOptionUpdate, ProductMinimal

__all__ = [
    "ProductOut", "KitComponentOut",
    "CategoryBase", "CategoryOut",
    "Variant", "VariantCreate", "VariantUpdate",
    "VariantOption", "VariantOptionCreate", "VariantOptionUpdate",
    "ProductVariantLink", "ProductVariantLinkCreate", "ProductVariantLinkUpdate",
    "ProductMinimal",  # 👈 adiciona aqui
]