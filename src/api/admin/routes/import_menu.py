from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks

from src.api.admin.services import menu_import_service
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, get_current_user
from src.core.models import User


router = APIRouter(prefix="/stores/{store_id}/import", tags=["Import"])

@router.post("/menu-from-images")
async def import_menu_from_images(
    store: GetStoreDep,
    db: GetDBDep,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    files: List[UploadFile] = File(..., description="Uma ou mais imagens do cardápio para processar."),
):
    """
    Recebe imagens de um cardápio, inicia o processamento com IA em background
    e retorna uma resposta imediata.
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Nenhum arquivo de imagem foi enviado."
        )

    file_data_list = [
        {"content": await file.read(), "content_type": file.content_type}
        for file in files
    ]

    background_tasks.add_task(
        menu_import_service.process_menu_with_openai,
        db=db,
        store_id=store.id,
        user_id=current_user.id,
        file_data_list=file_data_list
    )

    return {
        "message": "Recebemos seu cardápio! Já estamos analisando as imagens e em breve os produtos aparecerão no seu painel."
    }