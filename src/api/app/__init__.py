from fastapi import APIRouter

from src.api.app.routes.auth import router as auth_router
from src.api.app.routes.products import router as products_router  # importe o router de produtos

router = APIRouter(prefix="/app")

# Inclua os routers filhos no router pai
router.include_router(auth_router)
router.include_router(products_router)  # adicione o router de produtos aqui
