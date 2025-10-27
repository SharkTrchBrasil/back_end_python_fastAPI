# src/api/admin/routes/print_layouts.py (NOVO ARQUIVO)

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.print.print_layout import PrintLayoutConfigOut, PrintLayoutConfigUpdate

router = APIRouter(
    prefix="/stores/{store_id}/print-layouts",
    tags=["Print Layouts"]
)

@router.get("/{layout_type}", response_model=PrintLayoutConfigOut)
def get_print_layout_config(
    store: GetStoreDep,
    layout_type: str, # 'expedition' ou 'kitchen'
    db: GetDBDep,
):
    """
    Busca a configuração de layout para um tipo específico.
    Se não existir, cria e retorna uma configuração padrão.
    """
    if layout_type not in ["expedition", "kitchen"]:
        raise HTTPException(status_code=400, detail="Tipo de layout inválido. Use 'expedition' ou 'kitchen'.")

    # Tenta buscar a configuração existente
    config = db.query(models.PrintLayoutConfig).filter(
        models.PrintLayoutConfig.store_id == store.id,
        models.PrintLayoutConfig.destination == layout_type
    ).first()

    # Se não existir, cria uma padrão na hora
    if not config:
        config = models.PrintLayoutConfig(
            store_id=store.id,
            destination=layout_type
            # Os outros campos usarão os valores `default` definidos no modelo
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return config


@router.put("/{layout_type}", response_model=PrintLayoutConfigOut)
def save_print_layout_config(
    store: GetStoreDep,
    layout_type: str,
    payload: PrintLayoutConfigUpdate,
    db: GetDBDep,
):
    """
    Cria ou atualiza a configuração de layout para um tipo específico.
    """
    if layout_type not in ["expedition", "kitchen"]:
        raise HTTPException(status_code=400, detail="Tipo de layout inválido. Use 'expedition' ou 'kitchen'.")

    config = db.query(models.PrintLayoutConfig).filter(
        models.PrintLayoutConfig.store_id == store.id,
        models.PrintLayoutConfig.destination == layout_type
    ).first()

    if not config:
        config = models.PrintLayoutConfig(
            store_id=store.id,
            destination=layout_type
        )
        db.add(config)

    # Atualiza os campos com base no payload recebido
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config