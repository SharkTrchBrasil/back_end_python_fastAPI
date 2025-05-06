import os

import resend

from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis do .env

resend.api_key = api_key=os.getenv("RESEND_API_KEY")
print(f"Resend API Key being used: '{api_key}'")  # Adicione esta linha

def send_verification_email(to_email: str, token: str):
    verify_link = f"https://food.zapdelivery.online/verify-email?token={token}"
    return resend.Emails.send({
        "from": "Acme <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "Verifique seu e-mail",
        "html": f"""
            <p>Olá!</p>
            <p>Para ativar sua conta, clique no link abaixo:</p>
            <a href="{verify_link}">Verificar e-mail</a>
        """
    })





