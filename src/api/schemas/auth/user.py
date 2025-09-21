# Em schemas/user.py
import re
from typing import Optional
from datetime import date
from pydantic import BaseModel, Field, ConfigDict


# --- Schema de Leitura (Saída da API) ---
# O que a API retorna quando se pede os dados de um usuário
class UserSchema(BaseModel):
    id: int
    email: str
    name: str
    phone: str | None = None
    cpf: str | None = None
    birth_date: date | None = None

    is_superuser: bool
    referral_code: str
    model_config = ConfigDict(from_attributes=True)



class UserCreate(BaseModel):
    email: str
    name: str = Field(..., min_length=3)
    phone: str
    password: str = Field(..., min_length=8)

    # ✅ CAMPO ADICIONADO: Opcional, para o novo usuário inserir o código de quem o indicou
    referral_code: str | None = None


# --- Schema de Atualização (Entrada da API) ---
# O que o Flutter envia no wizard para atualizar o perfil do responsável
class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=3)
    phone: str | None = None

    # ✅ CAMPOS ADICIONADOS: Para salvar os dados do responsável
    cpf: str | None = None
    birth_date: date | None = None  # A API espera receber no formato "AAAA-MM-DD"


# --- Outros Schemas (sem alteração) ---
class ChangePasswordData(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class ResendEmail(BaseModel):
    email: str