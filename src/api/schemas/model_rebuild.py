# src/api/schemas/model_rebuild.py
"""
Arquivo para resolver referências circulares após importação de todos os schemas.
DEVE ser importado por último na inicialização do FastAPI.
"""


def rebuild_all_models():
    """
    Reconstrói todos os modelos com referências circulares na ordem correta.
    A ordem é crucial para evitar erros de definição.
    """

    try:
        # 1. PRIMEIRO: Importar schemas base (sem dependências circulares)
        from .base_schema import AppBaseModel
        from .rating.rating import RatingsSummaryOut
        from .category.category import CategoryOut
        from .category.product_category_link import ProductCategoryLinkOut, ProductCategoryLinkCreate

        # 2. SEGUNDO: Importar e reconstruir VariantOption (depende de ProductOut via TYPE_CHECKING)
        from .variant.variant_option import VariantOption
        from .variant.variant_option_wizard import VariantOptionCreateInWizard

        # 3. TERCEIRO: Importar e reconstruir Variant (depende de VariantOption)
        from .variant.variant import Variant, VariantCreateInWizard

        # 4. QUARTO: Importar ProductVariantLink (depende de Variant)
        from .product.product_variant_link import ProductVariantLink, ProductVariantLinkCreate

        # 5. QUINTO: Importar KitComponent (depende de ProductOut)
        from .product.kit_component import KitComponentOut

        # 6. SEXTO: Importar e reconstruir ProductOut (depende de todos os anteriores)
        from .product.product import ProductOut, ProductWizardCreate

        # 7. SÉTIMO: Importar schemas de Store (dependem de vários outros)
        from .store.store import StoreSchema, StoreWithRole
        from .store.store_details import StoreDetails

        # AGORA RECONSTRUIR NA ORDEM CORRETA:

        # Reconstruir primeiro os schemas que são dependências
        print("🔄 Reconstruindo VariantOption...")
        VariantOption.model_rebuild()

        print("🔄 Reconstruindo Variant...")
        Variant.model_rebuild()

        print("🔄 Reconstruindo ProductVariantLink...")
        ProductVariantLink.model_rebuild()

        print("🔄 Reconstruindo KitComponentOut...")
        KitComponentOut.model_rebuild()

        # Por último, reconstruir ProductOut (que referencia todos os outros)
        print("🔄 Reconstruindo ProductOut...")
        ProductOut.model_rebuild()

        print("🔄 Reconstruindo ProductWizardCreate...")
        ProductWizardCreate.model_rebuild()

        # Reconstruir schemas de Store
        print("🔄 Reconstruindo StoreSchema...")
        StoreSchema.model_rebuild()

        print("🔄 Reconstruindo StoreDetails...")
        StoreDetails.model_rebuild()

        print("✅ Todos os modelos Pydantic foram reconstruídos com sucesso!")

    except ImportError as e:
        print(f"⚠️ Erro de importação ao reconstruir modelos: {e}")
        print("Verifique se todos os arquivos de schema existem e estão corretos.")
    except Exception as e:
        print(f"❌ Erro inesperado ao reconstruir modelos: {e}")
        raise