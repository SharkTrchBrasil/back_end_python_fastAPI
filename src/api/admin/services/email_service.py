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
        "subject": "Seu código PDVix chegou! Confirme seu registro",
        "html": f"""
            <p>Olá!</p>
            <p>Para completar seu registro no PDVix, utilize o seguinte código:</p>
            <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; text-align: center;">
                <h2 style="font-size: 36px; color: #sua_cor_primaria; margin: 0;">{code}</h2>
            </div>
            <p>Copie e cole este código na tela de confirmação do PDVix para começar a usar todas as funcionalidades!</p>
            <p>Caso não tenha se registrado no PDVix, ignore esta mensagem.</p>
            <br>
            <p>Atenciosamente,</p>
            <p>A Equipe PDVix</p>
        """
    }
    email: resend.Email = resend.Emails.send(params)
    return email
