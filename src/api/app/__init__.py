from fastapi import APIRouter

from src.api.app.routes.auth import router as auth_router

router = APIRouter(prefix="/app")
router.include_router(auth_router)