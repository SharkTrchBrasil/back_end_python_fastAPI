from datetime import timedelta
from src.core.security import create_access_token

def generate_long_lived_token():
    # IMPORTANTE: Coloque aqui o email/identificador do seu usuário de serviço
    # que você criou no banco de dados.
    service_account_email = "chatbot-service@system.local"

    # Define a data de expiração para 10 anos a partir de agora
    expires = timedelta(days=365 * 10)

    # Prepara os dados para o token. O FastAPI espera o email no campo "sub".
    token_data = {"sub": service_account_email}

    # Gera o token usando a sua função
    long_lived_token = create_access_token(data=token_data, expires_delta=expires)

    print("--- SEU TOKEN DE LONGA DURAÇÃO ---")
    print(long_lived_token)
    print("--- COPIE O TOKEN ACIMA E COLE NA VARIÁVEL 'INTERNAL_AUTH_TOKEN' NA RAILWAY ---")

if __name__ == "__main__":
    generate_long_lived_token()