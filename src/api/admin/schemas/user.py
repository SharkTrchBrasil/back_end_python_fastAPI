import re
from typing import Optional

from pydantic import BaseModel, Field, validator


class User(BaseModel):
    id: int
    email: str
    name: str
    phone: str


class UserCreate(BaseModel):
    email: str
    name: str = Field(..., min_length=3, max_length=32)
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=8, max_length=16)



    @validator('phone')
    def validate_phone(self, v):
        if not re.fullmatch(r'^[1-9]{2}9\d{8}$', v):
            raise ValueError('Número de celular inválido. Use o formato DDD + 9 dígitos, ex: 11987654321')
        return v


class ChangePasswordData(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=16)


class ResendEmail(BaseModel):
    email: str


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=32)
    phone: Optional[str]
