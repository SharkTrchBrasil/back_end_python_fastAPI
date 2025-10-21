# src/api/admin/routes/zipcode.py (ATUALIZAR)

from fastapi import APIRouter, HTTPException
import requests
from typing import Optional

from src.api.schemas.store.location.zipcode_address import ZipcodeAddress

from src.core.dependencies import GetCurrentUserDep
from src.core.utils.geocoding.geocoding import GeocodingService

router = APIRouter(tags=["Zipcodes"], prefix="/zipcodes")


@router.get("/{zipcode}", response_model=ZipcodeAddress)
def get_zipcode(
        zipcode: str,
        _: GetCurrentUserDep,
):
    """
    ✅ VERSÃO MELHORADA: Busca endereço + coordenadas automaticamente
    """
    # 1. Busca dados do CEP
    result = requests.get(f'https://viacep.com.br/ws/{zipcode}/json/').json()

    if 'erro' in result:
        raise HTTPException(status_code=404, detail="CEP não encontrado")

    # 2. ✅ NOVO: Busca coordenadas automaticamente
    coordinates = GeocodingService.get_coordinates_from_address(
        street=result.get('logradouro', ''),
        number='',
        neighborhood=result.get('bairro', ''),
        city=result.get('localidade', ''),
        state=result.get('uf', '')
    )

    # 3. Adiciona coordenadas ao resultado
    if coordinates:
        result['latitude'] = coordinates[0]
        result['longitude'] = coordinates[1]

    return result