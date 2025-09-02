# routers/segments.py

from fastapi import APIRouter, HTTPException, status
from typing import List

from src.api.schemas.store.segment import SegmentSchema, SegmentCreate
from src.core.database import GetDBDep
from src.core.models import Segment

# Cria um "roteador" para organizar os endpoints relacionados a segmentos
router = APIRouter(
    prefix="/segments",  # Todas as rotas aqui começarão com /segments
    tags=["Segments"]  # Agrupa na documentação automática
)


@router.get(
    "/",
    response_model=List[SegmentSchema],
    summary="Listar todas as especialidades ativas"
)
def get_all_active_segments( db: GetDBDep):
    """
    Retorna uma lista de todas as especialidades (segmentos)
    que estão marcadas como ativas.

    Esta é a rota que seu app Flutter deve consumir no wizard de configuração.
    """
    segments = db.query(Segment).filter(Segment.is_active == True).all()
    return segments


@router.post(
    "/",
    response_model=SegmentSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Criar uma nova especialidade"
)
def create_new_segment(segment_data: SegmentCreate,db: GetDBDep):
    """
    Cria uma nova especialidade no banco de dados.
    Verifica se o nome já existe para evitar duplicatas.
    """
    # Verifica se já existe um segmento com o mesmo nome
    existing_segment = db.query(Segment).filter(Segment.name == segment_data.name).first()
    if existing_segment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A especialidade '{segment_data.name}' já existe."
        )

    # Cria a nova instância no banco de dados
    new_segment = Segment(**segment_data.model_dump())
    db.add(new_segment)
    db.commit()
    db.refresh(new_segment)

    return new_segment