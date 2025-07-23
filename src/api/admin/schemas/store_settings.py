from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class StoreSettingsBase(BaseModel):
    # Campos existentes
    is_delivery_active: Optional[bool] = True
    is_takeout_active: Optional[bool] = True
    is_table_service_active: Optional[bool] = True
    is_store_open: Optional[bool] = True
    auto_accept_orders: Optional[bool] = False
    auto_print_orders: Optional[bool] = False

    # ✅ NOVOS CAMPOS ADICIONADOS
    # Armazena a chave de destino da impressora principal (ex: "balcao")
    main_printer_destination: Optional[str] = None

    # Armazena a chave de destino da impressora da cozinha
    kitchen_printer_destination: Optional[str] = None

    # Você pode adicionar mais campos aqui no futuro, se necessário
    bar_printer_destination: Optional[str] = None

    # A configuração do Pydantic para ler dados de objetos SQLAlchemy
    model_config = ConfigDict(from_attributes=True)