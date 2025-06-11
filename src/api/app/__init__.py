from fastapi import APIRouter

from src.api.app.routes.auth import router as auth_router
from src.api.app.routes.products import router as products_router


router = APIRouter(prefix="/app")


router.include_router(auth_router)
router.include_router(products_router)  # adicione o router de produtos aqui

