from fastapi import APIRouter

from src.api.app.routes.auth import router as auth_router
from src.api.app.routes.products import router as products_router
from src.api.app.routes.customers import  router as customers_router
from src.api.app.routes.banners import router as banners_router
from src.api.app.routes.store_ratings import router as store_ratings_router
from src.api.app.routes.product_ratings import router as product_ratings_router
from src.api.app.routes.Store_cities_neig import router as store_cities_router
from  src.api.app.routes.wallet import router as wallet_router

router = APIRouter(prefix="/app")

# Inclua os routers filhos no router pai
router.include_router(auth_router)
router.include_router(products_router)  # adicione o router de produtos aqui
router.include_router(customers_router)

router.include_router(banners_router)
router.include_router(store_ratings_router)
router.include_router(product_ratings_router)
router.include_router(store_cities_router)
router.include_router(wallet_router)
