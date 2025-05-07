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
        "subject": "{code} é o código de confirmação do registro do seu PDVix",
        "html": f"""
            <p>Olá!</p>
            <p><h2 style="font-size: 32px; color: #4CAF50;">{code}</h2> é o código de confirmação do registro do seu PDVix</p>
            
            <p>Digite o código acima na tela do PDVix para confirmar o registro e começar a gerenciar sua loja com muito mais facilidade e eficiência!</p>
            <p>Se você não solicitou esse cadastro, ignore este e-mail.</p>
               <p>Se você não solicitou este registro, ignore este e-mail.</p>
            <p>Atenciosamente,</p>
            <p>Equipe PDVix</p>
        """
    }
    email: resend.Email = resend.Emails.send(params)
    return email
