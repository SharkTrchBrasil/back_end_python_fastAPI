# No seu arquivo de schemas Pydantic de Horários

from pydantic import BaseModel
from typing import Optional

# ✅ 1. Crie um schema base com os campos comuns
class StoreHoursBase(BaseModel):
    day_of_week: int
    open_time: str
    close_time: str
    shift_number: int
    is_active: bool

# ✅ 2. Crie um schema para RECEBER dados do frontend, que herda do base.
#    Note que ele não tem 'id' ou 'store_id'.
class StoreHoursCreate(StoreHoursBase):
    pass

# ✅ 3. Renomeie seu schema antigo para ser o schema de SAÍDA, que inclui os campos do banco.
class StoreHoursOut(StoreHoursBase):
    id: int
    store_id: int

    model_config = {
        "from_attributes": True
    }