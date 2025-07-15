from fastapi import APIRouter, HTTPException
import requests

from src.api.admin.schemas.zipcode_address import ZipcodeAddress
from src.core.dependencies import GetCurrentUserDep

router = APIRouter(tags=["Zipcodes"], prefix="/zipcodes")

@router.get("/{zipcode}", response_model=ZipcodeAddress)
def get_zipcode(
        zipcode: str,
        _: GetCurrentUserDep,
):
    result = requests.get(f'https://viacep.com.br/ws/{zipcode}/json/').json()
    if 'erro' in result:
        raise HTTPException(status_code=404, detail="CEP não encontrado")
    return result
