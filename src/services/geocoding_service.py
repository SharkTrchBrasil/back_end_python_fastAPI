"""
Serviço de Geocoding para obter coordenadas a partir de endereços.
Usa o serviço de geocoding existente (Nominatim/OpenStreetMap gratuito).
"""
import logging
from typing import Optional, Tuple

# Importa o serviço existente
from src.core.utils.geocoding.geocoding import GeocodingService as CoreGeocodingService

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Serviço para obter coordenadas geográficas (latitude, longitude) 
    a partir do nome de cidade/bairro.
    
    Usa Nominatim (OpenStreetMap) - gratuito, com limite de 1 request/segundo.
    Se não conseguir obter coordenadas, retorna None (opcional).
    """
    
    @staticmethod
    async def geocode_city(city_name: str, state: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """
        Obtém coordenadas de uma cidade usando geocoding gratuito.
        
        Args:
            city_name: Nome da cidade
            state: Estado (opcional, para maior precisão)
            
        Returns:
            Tuple (latitude, longitude) ou None se não conseguir obter
        """
        try:
            # Monta o endereço: "Cidade, Estado, Brazil"
            address_parts = [city_name]
            if state:
                address_parts.append(state)
            address_parts.append("Brazil")
            
            full_address = ", ".join(address_parts)
            
            # Usa o serviço de geocoding existente
            coordinates = CoreGeocodingService.get_coordinates_from_address(
                street="",
                number="",
                neighborhood="",
                city=city_name,
                state=state or "",
            )
            
            if coordinates:
                logger.info(f"✅ Coordenadas obtidas para cidade {city_name}: {coordinates}")
                return coordinates
            else:
                logger.warning(f"⚠️ Não foi possível obter coordenadas para cidade {city_name}")
                return None
                
        except Exception as e:
            logger.warning(f"❌ Erro ao obter coordenadas para cidade {city_name}: {e}")
            return None
    
    @staticmethod
    async def geocode_neighborhood(
        neighborhood_name: str, 
        city_name: str, 
        state: Optional[str] = None
    ) -> Optional[Tuple[float, float]]:
        """
        Obtém coordenadas de um bairro usando geocoding gratuito.
        
        Args:
            neighborhood_name: Nome do bairro
            city_name: Nome da cidade
            state: Estado (opcional)
            
        Returns:
            Tuple (latitude, longitude) ou None se não conseguir obter
        """
        try:
            # Usa o serviço de geocoding existente com bairro
            coordinates = CoreGeocodingService.get_coordinates_from_address(
                street="",
                number="",
                neighborhood=neighborhood_name,
                city=city_name,
                state=state or "",
            )
            
            if coordinates:
                logger.info(f"✅ Coordenadas obtidas para bairro {neighborhood_name}, {city_name}: {coordinates}")
                return coordinates
            else:
                logger.warning(f"⚠️ Não foi possível obter coordenadas para bairro {neighborhood_name}, {city_name}")
                return None
                
        except Exception as e:
            logger.warning(f"❌ Erro ao obter coordenadas para bairro {neighborhood_name}: {e}")
            return None

