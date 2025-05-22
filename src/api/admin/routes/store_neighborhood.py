from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StoreNeighborhood, StoreCity
from src.api.admin.schemas.store_neighborhood import StoreNeighborhoodSchema

router = APIRouter(prefix="/cities/{city_id}/neighborhoods", tags=["Neighborhoods"])


@router.post("", response_model=StoreNeighborhoodSchema)
def create_neighborhood(
    city_id: int,
    db: Session = GetDBDep,
    store = GetStoreDep,
    name: str = Form(...),
    delivery_fee: int = Form(0),
    free_delivery: bool = Form(False),
    is_active: bool = Form(True),
):
    # Verifica se a cidade pertence à loja do usuário
    city = db.query(StoreCity).filter(StoreCity.id == city_id, StoreCity.store_id == store.id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found or does not belong to the store")

    neighborhood = StoreNeighborhood(
        name=name,
        city_id=city_id,
        delivery_fee=delivery_fee,
        free_delivery=free_delivery,
        is_active=is_active,
    )
    db.add(neighborhood)
    db.commit()
    db.refresh(neighborhood)
    return neighborhood


@router.get("", response_model=list[StoreNeighborhoodSchema])
def list_neighborhoods(
    city_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
):
    # Só retorna bairros da cidades que pertencem à loja
    city = db.query(StoreCity).filter(StoreCity.id == city_id, StoreCity.store_id == store.id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found or does not belong to the store")

    neighborhoods = db.query(StoreNeighborhood).filter(StoreNeighborhood.city_id == city_id).all()
    return neighborhoods


@router.get("/{neighborhood_id}", response_model=StoreNeighborhoodSchema)
def get_neighborhood(
    city_id: int,
    neighborhood_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
):
    neighborhood = (
        db.query(StoreNeighborhood)
        .join(StoreCity, StoreNeighborhood.city_id == StoreCity.id)
        .filter(
            StoreNeighborhood.id == neighborhood_id,
            StoreNeighborhood.city_id == city_id,
            StoreCity.store_id == store.id,
        )
        .first()
    )
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")
    return neighborhood


@router.patch("/{neighborhood_id}", response_model=StoreNeighborhoodSchema)
def update_neighborhood(
    city_id: int,
    neighborhood_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
    name: str | None = Form(None),
    delivery_fee: int | None = Form(None),
    free_delivery: bool | None = Form(None),
    is_active: bool | None = Form(None),
):
    neighborhood = (
        db.query(StoreNeighborhood)
        .join(StoreCity, StoreNeighborhood.city_id == StoreCity.id)
        .filter(
            StoreNeighborhood.id == neighborhood_id,
            StoreNeighborhood.city_id == city_id,
            StoreCity.store_id == store.id,
        )
        .first()
    )
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    if name is not None:
        neighborhood.name = name
    if delivery_fee is not None:
        neighborhood.delivery_fee = delivery_fee
    if free_delivery is not None:
        neighborhood.free_delivery = free_delivery
    if is_active is not None:
        neighborhood.is_active = is_active

    db.commit()
    db.refresh(neighborhood)
    return neighborhood


@router.delete("/{neighborhood_id}", status_code=204)
def delete_neighborhood(
    city_id: int,
    neighborhood_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
):
    neighborhood = (
        db.query(StoreNeighborhood)
        .join(StoreCity, StoreNeighborhood.city_id == StoreCity.id)
        .filter(
            StoreNeighborhood.id == neighborhood_id,
            StoreNeighborhood.city_id == city_id,
            StoreCity.store_id == store.id,
        )
        .first()
    )
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    db.delete(neighborhood)
    db.commit()
