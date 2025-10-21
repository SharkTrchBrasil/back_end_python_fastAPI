# src/api/utils/geocoding.py (NOVO ARQUIVO)

import requests
from typing import Optional, Tuple


class GeocodingService:
    """
    Serviço de geocoding gratuito usando Nominatim (OpenStreetMap)
    Limite: 1 request/segundo (suficiente para cadastro de lojas)
    """

    BASE_URL = "https://nominatim.openstreetmap.org/search"

    @staticmethod
    def get_coordinates_from_address(
            street: str,
            number: str,
            neighborhood: str,
            city: str,
            state: str,
            country: str = "Brazil"
    ) -> Optional[Tuple[float, float]]:
        """
        Converte endereço em coordenadas (latitude, longitude)
        Retorna None se não encontrar
        """
        # Monta query de endereço
        address_parts = [
            f"{street}, {number}" if number else street,
            neighborhood,
            city,
            state,
            country
        ]

        full_address = ", ".join(filter(None, address_parts))

        try:
            response = requests.get(
                GeocodingService.BASE_URL,
                params={
                    "q": full_address,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "br",  # Força resultados do Brasil
                },
                headers={
                    "User-Agent": "MenuHub/1.0"  # Obrigatório para Nominatim
                },
                timeout=5
            )

            if response.status_code == 200 and response.json():
                result = response.json()[0]
                lat = float(result["lat"])
                lon = float(result["lon"])

                return (lat, lon)

            return None

        except Exception as e:
            print(f"❌ Erro no geocoding: {e}")
            return None

    @staticmethod
    def get_coordinates_from_cep(cep: str) -> Optional[Tuple[float, float]]:
        """
        Busca coordenadas a partir do CEP usando ViaCEP + Geocoding
        """
        try:
            # 1. Busca endereço pelo CEP
            cep_clean = cep.replace("-", "").replace(".", "")
            viacep_response = requests.get(
                f"https://viacep.com.br/ws/{cep_clean}/json/"
            )

            if viacep_response.status_code != 200:
                return None

            address_data = viacep_response.json()

            if "erro" in address_data:
                return None

            # 2. Converte endereço em coordenadas
            coords = GeocodingService.get_coordinates_from_address(
                street=address_data.get("logradouro", ""),
                number="",  # CEP não tem número
                neighborhood=address_data.get("bairro", ""),
                city=address_data.get("localidade", ""),
                state=address_data.get("uf", "")
            )

            return coords

        except Exception as e:
            print(f"❌ Erro ao buscar coordenadas do CEP: {e}")
            return None