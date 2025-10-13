# Em schemas/user.py
import re
from typing import Optional
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, EmailStr, validator


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




class CreateStoreUserRequest(BaseModel):
    """Schema para criação de um novo usuário diretamente vinculado a uma loja."""

    name: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6)
    role_machine_name: str = Field(..., description="Nome técnico da função (ex: 'manager', 'cashier')")

    @validator('phone')
    def validate_phone(cls, v):
        # Remove caracteres não numéricos
        phone_clean = re.sub(r'\D', '', v)
        if len(phone_clean) < 10 or len(phone_clean) > 11:
            raise ValueError('Telefone deve ter 10 ou 11 dígitos')
        return phone_clean

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Senha deve ter no mínimo 6 caracteres')
        return v