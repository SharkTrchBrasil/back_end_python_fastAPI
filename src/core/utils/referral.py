# src/core/utils/referral.py

import random
import string
from sqlalchemy.orm import Session

from src.core import models


def generate_unique_referral_code(db, name: str) -> str:
    """
    Gera um código de indicação único a partir do nome do usuário.
    Ex: "João" -> "JOAO1234"
    Garante que o código gerado não exista no banco de dados.
    """
    # Pega o primeiro nome, converte para maiúsculas e remove caracteres especiais
    base_name = ''.join(filter(str.isalpha, name.split()[0])).upper()[:5]

    while True:
        # Gera 4 dígitos aleatórios
        random_part = ''.join(random.choices(string.digits, k=4))
        code = f"{base_name}{random_part}"

        # Verifica se o código já existe no banco
        exists = db.query(models.User).filter(models.User.referral_code == code).first()
        if not exists:
            return code