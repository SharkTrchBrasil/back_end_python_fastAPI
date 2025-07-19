# src/core/db_initialization.py
from sqlalchemy.orm import Session
from src.core import models
from datetime import datetime, timezone # Importe datetime e timezone para timestamps

def initialize_roles(db: Session):
    """
    Verifica a existência de roles padrão e as cria se não existirem.
    """
    roles_to_ensure = ['owner', 'manager', 'cashier', 'stockManager']
    existing_roles = db.query(models.Role.machine_name).all()
    existing_roles_names = {role[0] for role in existing_roles} # Converte para set para busca rápida

    new_roles = []
    for role_name in roles_to_ensure:
        if role_name not in existing_roles_names:
            print(f"Role '{role_name}' não encontrada. Criando...")
            new_roles.append(
                models.Role(
                    machine_name=role_name,
                    created_at=datetime.now(timezone.utc), # Use timezone.utc para timestamps consistentes
                    updated_at=datetime.now(timezone.utc)
                )
            )
        else:
            print(f"Role '{role_name}' já existe.")

    if new_roles:
        db.add_all(new_roles)
        db.commit()
        print("Roles padrão criadas/verificadas com sucesso.")
    else:
        print("Todas as roles padrão já existem.")