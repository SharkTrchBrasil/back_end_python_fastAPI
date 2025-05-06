from fastapi import APIRouter

from src.api.admin.routes.stores import router as stores_router
from src.api.admin.routes.products import router as products_router
from src.api.admin.routes.users import router as users_router
from src.api.admin.routes.auth import router as auth_router
from src.api.admin.routes.categories import router as categories_router
from src.api.admin.routes.variants import router as variants_router
from src.api.admin.routes.variant_options import router as options_router
from src.api.admin.routes.coupons import router as coupons_router
from src.api.admin.routes.totems import router as totems_router
from src.api.admin.routes.themes import router as themes_router





from src.api.admin.routes.suppliers import router as suppliers_router
from src.api.admin.routes.payment_methods import router as payment_methods_router
from src.api.admin.routes.store_hours import router as store_hours_router
router = APIRouter(prefix="/admin")
router.include_router(stores_router)
router.include_router(products_router)
router.include_router(users_router)
router.include_router(auth_router)
router.include_router(categories_router)
router.include_router(variants_router)
router.include_router(options_router)

router.include_router(coupons_router)
router.include_router(totems_router)
router.include_router(themes_router)





#minhas features
router.include_router(suppliers_router)
router.include_router(payment_methods_router)
router.include_router(store_hours_router)


