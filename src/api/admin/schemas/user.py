from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    email: str
    name: str
    phone: str
    is_active: bool
    is_email_verified:bool
    verification_token: str


class UserCreate(BaseModel):
    email: str
    name: str = Field(..., min_length=3, max_length=32)
    phone: str
    password: str = Field(..., min_length=8, max_length=16)
    is_active: bool
    is_email_verified: bool



class ChangePasswordData(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=16)