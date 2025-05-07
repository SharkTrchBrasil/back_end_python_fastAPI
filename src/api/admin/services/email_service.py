import resend
from typing import Dict
from fastapi import FastAPI
from src.core.config import config

resend.api_key = config.RESEND_API_KEY


print(f"Resend API Key being used: '{resend.api_key}'")  # Use resend.api_key diretamente

app = FastAPI()

def send_verification_email(to_email: str, code: str) -> Dict:
    params: resend.Emails.SendParams = {
        "from": "Zap Delivery <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "Código de verificação do seu e-mail",
        "html": f"""
            <p>Olá!</p>
            <p>Seu código de verificação é:</p>
            <h2 style="font-size: 32px; color: #4CAF50;">{code}</h2>
            <p>Digite este código no app para concluir seu cadastro.</p>
            <p>Se você não solicitou esse cadastro, ignore este e-mail.</p>
        """
    }
    email: resend.Email = resend.Emails.send(params)
    return email
