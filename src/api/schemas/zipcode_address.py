from pydantic import BaseModel, Field


class ZipcodeAddress(BaseModel):
    zipcode: str = Field(..., validation_alias="cep")
    city: str = Field(..., validation_alias="localidade")
    state: str = Field(..., validation_alias="uf")
    neighborhood: str = Field(..., validation_alias="bairro")
    street: str = Field(..., validation_alias="logradouro")