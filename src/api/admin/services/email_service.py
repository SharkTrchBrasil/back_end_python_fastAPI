import os

import resend

from typing import Dict
from fastapi import FastAPI
from src.core.config import config

resend.api_key = config.RESEND_API_KEY


print(f"Resend API Key being used: '{resend.api_key}'")  # Use resend.api_key diretamente

app = FastAPI()

def send_verification_email(to_email: str, token: str) -> Dict:
    verify_link = f"https://food.zapdelivery.online/verify-email?token={token}"
    params: resend.Emails.SendParams = {
        "from": "Acme <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "Verifique seu e-mail",
        "html": f"""
            <p>Olá!</p>
            <p>Para ativar sua conta, clique no link abaixo:</p>
            <a href="{verify_link}">Verificar e-mail</a>
        """
    }
    email: resend.Email = resend.Emails.send(params)
    return email

