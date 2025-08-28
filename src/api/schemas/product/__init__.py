# schemas/product/__init__.py
from .product import ProductOut, ProductWizardCreate
from .product_variant_link import ProductVariantLink, ProductVariantLinkCreate, ProductVariantLinkUpdate
from .kit_component import KitComponentOut
  # Mantenha apenas o Create aqui

__all__ = [
    'ProductOut',
    'ProductWizardCreate',
    'ProductVariantLink',
    'ProductVariantLinkCreate',
    'ProductVariantLinkUpdate',
    'KitComponentOut',

]